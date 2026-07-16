#!/usr/bin/env python3
"""
ODM Defaults Classifier
========================
Joins ODM Defaults.csv (from odm_defaults.py) with the Direct Master CSV
(from direct_reader.py) to classify each default rule as:

  - System   → goes into RE as C# DefaultRuleCollection classes
  - Business → goes into SQL database
  - Review   → cannot auto-classify, needs human decision

Classification rules:
  1. Default Value = "" (empty string)  → System  (cleaning/reset logic)
  2. Control Type in Direct = Checkbox  → System
  3. Control Type in Direct = Stepper   → System  (0/1 numeric stepper)
  4. Display Rules contains "hidden"    → Business (hidden field default)
  5. Everything else                    → Review

Special flags raised:
  - Agent/Consumer divergence: same field, different default values per flow
  - Radio conflict: ODM has a default for a field Direct calls Radio — ask user
  - Control type conflict: ODM and Direct disagree on control type — ask user
  - ODM-only: field in Defaults.csv but not in Direct
  - Direct-only: field in Direct has a Default Value but no ODM rule

Inputs:
  --odm     Path to {prefix}_Defaults.csv (from odm_defaults.py)
  --direct  Path to Progressive_Direct_Master.csv (from direct_reader.py)
  --output  Output directory
  --prefix  Filename prefix (default: PGR)

Outputs:
  {prefix}_System_Defaults.csv      ← RE implementation targets
  {prefix}_Business_Defaults.csv    ← SQL database targets
  {prefix}_Review_Defaults.csv      ← needs human decision before proceeding
  {prefix}_Gaps_Report.csv          ← ODM-only, Direct-only, conflicts
  {prefix}_Agent_Consumer_Diff.csv  ← same field, different defaults by flow

Pipeline position:
  INPUT:  {prefix}_Defaults.csv  +  Progressive_Direct_Master.csv
  OUTPUT: System_Defaults.csv    →  re-defaults-codegen (Claude Code)
          Business_Defaults.csv  →  SQL import
  NEXT:   re-defaults-codegen (future Claude Code skill)
"""

import re, os, argparse
import pandas as pd


# ── Control Type Constants ────────────────────────────────────────────────────

# Direct Control Type values that classify as System default (singularized)
SYSTEM_CONTROL_TYPES = {
    'checkbox', 'check box',
    'stepper', 'numeric stepper', 'number stepper',
}

# Direct Control Type values that are Radio — flag if ODM has a default for these
RADIO_CONTROL_TYPES = {
    'radio', 'radio button', 'radiobutton',
    'segmented control', 'segmentedcontrol',
}


# ── Enum / value normalization (Issue #11e) ───────────────────────────────────
import json

def load_enum_norm(path: str) -> dict:
    """Load the field-scoped ODM-value → Direct-label map. Missing file → {}."""
    try:
        with open(path, encoding='utf-8-sig') as fh:
            return json.load(fh)
    except Exception:
        return {}


def norm_value(field_canonical: str, value: str, enum_map: dict) -> str:
    """
    Normalize a value for equality comparison. SAFE-only:
      1. field-scoped map (e.g. DwellingMedicalPayments: cov5000 → $5k)
      2. generic boolean (true→yes, false→no)
      3. cosmetic: lowercase, strip quotes/space/$/commas/%
    Deliberately does NOT strip semantic prefixes like 'cov' generically — a
    code→label equivalence must be listed explicitly in the map (per Bolt eng:
    `1` vs "Owner Occupied" is NOT auto-equivalent; `cov500` vs `$500` only if listed).
    """
    v = str(value or '').strip().strip('"').strip("'")
    if v == '' or v.lower() == 'nan':
        return ''
    fmap = enum_map.get(field_canonical, {}) or {}
    if v in fmap:                         # exact field-scoped ODM code → label
        v = fmap[v]
    gb = enum_map.get('_generic_boolean', {})
    if v.lower() in gb:                   # generic true/false → Yes/No
        v = gb[v.lower()]
    v = v.lower()
    for ch in ['$', ',', ' ', '%']:
        v = v.replace(ch, '')
    return v


# ── Join Key Helpers ──────────────────────────────────────────────────────────

def odm_field_to_canonical(field_name: str) -> str:
    """
    Strip PolicyData/ prefix from ODM field name to get canonical name.
    e.g. 'PolicyData/PLTypeOfFoundation' → 'PLTypeOfFoundation'
    Sub-paths like 'PolicyData/FQData/SomeField' → 'FQData/SomeField'
    """
    if not field_name or str(field_name).strip() in ('', 'nan', '(Stage-only rule)'):
        return ''
    s = str(field_name).strip()
    if s.startswith('PolicyData/'):
        return s[len('PolicyData/'):]
    return s


def normalize_ct(ct: str) -> str:
    """
    Lowercase, strip, singularize, AND map semantic synonyms to a canonical
    token so equivalent control types written differently don't read as a
    CONTROL-TYPE-CONFLICT.  (Issue #11a)

    Examples that now compare equal:
      'numeric' == 'input field (numeric)' == 'text field (numeric)'  → 'numeric'
      'text field' == 'input field' == 'free text'                    → 'text'
      'drop down' == 'select' == 'picker'                             → 'dropdown'
      'number stepper' == 'numeric stepper'                           → 'stepper'
    Note: 'stepper' (a +/- widget) stays distinct from 'numeric' (a typed
    numeric input) — those are genuinely different controls.
    """
    s = str(ct).strip().lower() if ct and str(ct).strip() not in ('', 'nan') else ''
    if not s:
        return ''
    s = s.replace('\\n', ' ').replace('\n', ' ').strip().strip('"').strip("'")
    s = re.sub(r'\s+', ' ', s).strip()

    # exact synonym groups → canonical token
    SYNONYMS = {
        'numeric':          {'numeric', 'input field (numeric)', 'text field (numeric)',
                             'numeric input', 'number input', 'numeric field', 'numeric text'},
        'text':             {'text', 'text field', 'input field', 'input field (text)',
                             'free text', 'text input', 'text box', 'textbox'},
        'dropdown':         {'dropdown', 'drop down', 'select', 'picker', 'combobox', 'combo box'},
        'date':             {'date', 'date picker', 'datepicker', 'date field', 'calendar'},
        'stepper':          {'stepper', 'number stepper', 'numeric stepper'},
        'checkbox':         {'checkbox', 'check box'},
        'segmented control':{'segmented control', 'segmentedcontrol', 'segmented'},
        'radio':            {'radio', 'radio button', 'radiobutton'},
    }
    for canon, variants in SYNONYMS.items():
        if s in variants:
            return canon

    # substring canonicalization for messy real-world labels
    # ("Date Field with calendar", "Text fields (numeric)", "Number Stepper 0-9").
    # Order matters: more specific widgets first; 'numeric' before 'text';
    # 'date' before 'dropdown' so "date picker" → date.
    if 'stepper' in s:                                   return 'stepper'
    if 'checkbox' in s or 'check box' in s:              return 'checkbox'
    if 'segmented' in s:                                 return 'segmented control'
    if 'radio' in s:                                     return 'radio'
    if 'date' in s or 'calendar' in s:                   return 'date'
    if 'numeric' in s or 'number' in s:                  return 'numeric'
    if 'dropdown' in s or 'drop down' in s or 'picker' in s or 'select' in s: return 'dropdown'
    if 'text' in s:                                      return 'text'
    return s


# ── Classification Logic ──────────────────────────────────────────────────────

def classify_rule(odm_row: pd.Series, direct_row: pd.Series | None) -> tuple:
    """
    Returns (classification, reason, flags)
    classification: 'System' | 'Business' | 'Review'
    reason: human-readable explanation
    flags: list of special flag strings to surface in output
    """
    flags = []

    default_val = str(odm_row.get('Default Value', '') or '').strip()
    odm_ct      = normalize_ct(odm_row.get('Control Type', ''))
    visible     = str(odm_row.get('Visible', '') or '').strip().lower()
    disabled    = str(odm_row.get('Disabled', '') or '').strip().lower()

    # ── Rule 0: Disabled=true display-lock → NOT a value default ───────────────
    # A rule that re-shows a field greyed-out/locked (Disabled=true), often with
    # DefaultValue set to the field's own value, is a display-lock, not a business
    # default. Route out of the defaults set for the Relevancy/display stage. (Issue #11c / #2)
    if disabled == 'true':
        flags.append('DISABLED-DISPLAY-LOCK: Disabled=true — field is locked/greyed-out, '
                     'not a value default; belongs to relevancy/display, not defaults')
        return 'Review', 'Disabled=true display-lock — not a value default (route to relevancy)', flags

    # ── Rule 1: Cleaning logic ────────────────────────────────────────────────
    # Signal: DefaultValue is empty AND Visible=false.
    # When a parent/dependency field changes, the child field is hidden
    # (Visible=false) and its value wiped (DefaultValue=""). This resets
    # dependent input. Confirmed across the dataset: 101 rules match this,
    # independent of folder name. Always System.
    is_empty_default = (
        default_val in ('""', "''", '') or
        default_val.strip('"').strip("'") == ''
    )
    if is_empty_default and visible == 'false':
        return 'System', 'Cleaning logic — empty default + Visible=false (dependency reset)', flags

    # Empty default but NOT Visible=false → not cleaning, needs review
    # (e.g. CoSSN fields have empty default but Visible=true — different case)
    if is_empty_default:
        flags.append(
            'EMPTY-DEFAULT-NOT-HIDDEN: Default is empty but Visible is not false '
            f'(Visible={visible or "not set"}) — not standard cleaning logic, verify')
        return 'Review', 'Empty default without Visible=false — not standard cleaning', flags

    if direct_row is None:
        # No Direct match — cannot fully classify
        flags.append('ODM-ONLY: field not found in Direct — verify field is in scope')
        return 'Review', 'No Direct match — control type unknown, cannot classify', flags

    direct_ct   = normalize_ct(direct_row.get('Control Type', ''))
    display_rules = str(direct_row.get('Display Rules', '') or '').strip().lower()

    # ── Rule 2: Hidden field → Business ──────────────────────────────────────
    # Checked BEFORE control type — a hidden Checkbox/Stepper is still Business.
    # Hidden means the user never sees it; the default is a business-configured value.
    #
    # Two patterns:
    #   A) Literal: display rules contains the word "hidden"
    #      e.g. "Hidden Not for display and defaulted to 1"
    #      e.g. "Hidden If PL_F56_YearsAtAddress is more than 3"
    #
    #   B) Conditional: field is hidden for specific conditions that match the
    #      ODM rule's own conditions (e.g. hidden for specific states = Business
    #      for those states, even if the word "hidden" isn't in display rules)
    #      e.g. DogsBreedsSelection: "IF Dogs=True AND State NOT in [AZ,CO,...]"
    #           default "If state IS in [AZ,CO,...] defaulted to..."
    #           → field is hidden for those states → Business
    #
    # Pattern A: literal hidden keyword
    HIDDEN_KEYWORDS = ['hidden', 'not for display', 'not displayed', 'not visible',
                       'never shown', 'not shown']
    for kw in HIDDEN_KEYWORDS:
        if kw in display_rules:
            return 'Business', f'Hidden field (Display Rules: "{kw}")', flags

    # Pattern B: conditional hiding — default text itself references the hiding condition
    # Signals: default value mentions "if hidden", "when hidden", "if not displayed"
    default_lower = default_val.lower()
    CONDITIONAL_HIDDEN_SIGNALS = ['if hidden', 'when hidden', 'if not displayed',
                                  'if not shown', 'when not shown']
    for signal in CONDITIONAL_HIDDEN_SIGNALS:
        if signal in default_lower:
            return 'Business', \
                f'Conditionally hidden field — default text references hiding condition ("{signal}")', \
                flags

    # Pattern C: field is hidden in specific states/conditions — ODM default applies
    # exactly when field is hidden (conditions in ODM match hiding conditions in Direct).
    # Cannot auto-detect this — flag it for human confirmation.
    # Heuristic: display rules have conditions (AND/OR/IF) but no "hidden" keyword,
    # AND default value also references states or conditions → possible conditional hiding.
    has_conditions_in_display = any(kw in display_rules for kw in ['and', 'or', ' if ', 'state', 'when'])
    has_conditions_in_default = any(kw in default_lower for kw in ['state', 'if ', 'when ', 'lob'])
    if has_conditions_in_display and has_conditions_in_default:
        flags.append(
            'POSSIBLE-CONDITIONAL-HIDDEN: Display Rules have conditions and default also '
            'references conditions — field may be hidden for the cases where this default applies. '
            'If field is hidden for those conditions → Business. Please confirm.')

    # ── Computed-date default → tag before control-type logic (Issue #11b) ────
    # The parser renders computed dates into readable forms. Recognize them (and
    # cross-field date copies) here so they route consistently instead of getting
    # mislabeled as a control-type conflict or opaque "cannot classify".
    dl = default_val.lower()
    COMPUTED_DATE_SIGNALS = ["today's year", 'calculated date', 'as yyyy-mm-dd',
                             'purchasedate', 'yearsataddress', 'formatted as',
                             'month/15/year', '01/01/(', '1.1.(']
    is_cross_field_date = (direct_ct == 'date'
                           and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,}', default_val or '') is not None)
    if any(sig in dl for sig in COMPUTED_DATE_SIGNALS) or is_cross_field_date:
        flags.append(f'COMPUTED-DATE-DEFAULT: default is computed/cross-field ("{default_val[:60]}") — '
                     'verify date formula rather than treating as a literal value')
        return 'Review', 'Computed-date default — needs date-formula verification', flags

    # ── Rule 3/4: Checkbox or Stepper in Direct → System ─────────────────────
    if direct_ct in SYSTEM_CONTROL_TYPES:
        ct_label = direct_row.get('Control Type', direct_ct)
        if odm_ct and odm_ct != direct_ct and odm_ct not in ('', 'nan'):
            flags.append(
                f'CONTROL-TYPE-CONFLICT: ODM={odm_ct}, Direct={direct_ct} — Direct wins per convention, verify')
        return 'System', f'Control type is {ct_label} (Direct)', flags

    # ── Special: Radio/Segmented in Direct → flag, do not classify yet ────────
    # ODM encodes radio buttons as checkboxes — Direct is source of truth.
    # A default on a Radio field needs explicit decision — it may be Business
    # (if the field can be hidden) or may not belong at all.
    if direct_ct in RADIO_CONTROL_TYPES:
        flags.append(
            f'RADIO-CONFLICT: Direct says Radio/Segmented Controls, ODM has default '
            f'"{default_val}" — ODM treats radio as checkbox but Direct does not. '
            f'Please decide: (1) should this default exist in RE? '
            f'(2) if yes — is the field ever hidden? Hidden=Business, else needs decision.')
        return 'Review', 'Radio/Segmented question with ODM default — needs decision', flags

    # ── Control type conflict between ODM and Direct (non-checkbox) ──────────
    if odm_ct and direct_ct and odm_ct not in ('', 'nan') and direct_ct not in ('', 'nan'):
        if odm_ct != direct_ct:
            flags.append(
                f'CONTROL-TYPE-CONFLICT: ODM={odm_ct}, Direct={direct_ct} — '
                f'please decide which is correct before classifying')
            return 'Review', f'Control type conflict between ODM and Direct', flags

    # ── Default: cannot auto-classify ────────────────────────────────────────
    return 'Review', \
        f'Cannot auto-classify — Control Type={direct_ct or "unknown"}, ' \
        f'Display Rules="{display_rules[:80] or "none"}"', \
        flags


# ── Agent/Consumer Divergence Check ──────────────────────────────────────────

def find_agent_consumer_diffs(odm_df: pd.DataFrame, enum_map: dict = None) -> pd.DataFrame:
    """
    Find fields where Agent and Consumer have different default values.
    Values are enum/label-normalized before comparison so encoding-equivalent
    values (e.g. cov5000 vs $5k) don't read as a divergence. (Issue #11e)
    """
    enum_map = enum_map or {}
    # Only look at rows with actual default values
    has_default = odm_df[odm_df['Default Value'].notna() &
                         (odm_df['Default Value'].astype(str).str.strip() != '')]

    diffs = []
    fields = has_default['Canonical'].unique()

    for field in fields:
        rows = has_default[has_default['Canonical'] == field]
        agent_rows    = rows[rows['Flow'].isin(['Agent', 'Both'])]
        consumer_rows = rows[rows['Flow'].isin(['Consumer', 'Both'])]

        agent_vals    = {norm_value(field, v, enum_map) for v in agent_rows['Default Value'].astype(str)}
        consumer_vals = {norm_value(field, v, enum_map) for v in consumer_rows['Default Value'].astype(str)}

        # Remove empty
        agent_vals    = {v for v in agent_vals    if v not in ('', 'nan')}
        consumer_vals = {v for v in consumer_vals if v not in ('', 'nan')}

        if not agent_vals or not consumer_vals:
            continue

        if agent_vals != consumer_vals:
            # show the original (un-normalized) values for readability
            a_raw = sorted({str(v).strip() for v in agent_rows['Default Value'].astype(str) if str(v).strip() not in ('', 'nan')})
            c_raw = sorted({str(v).strip() for v in consumer_rows['Default Value'].astype(str) if str(v).strip() not in ('', 'nan')})
            diffs.append({
                'Field':          field,
                'Agent Default':  ', '.join(a_raw),
                'Consumer Default': ', '.join(c_raw),
                'Note': 'Same field, different defaults per flow (after normalization) — verify both are intentional',
            })

    return pd.DataFrame(diffs)


# ── Spelling / Near-Match Detection ───────────────────────────────────────────

def find_spelling_mismatches(odm_df: pd.DataFrame, direct_df: pd.DataFrame,
                             already_matched: set = None) -> pd.DataFrame:
    """
    For ODM default fields that don't match Direct exactly, find near-matches
    in Direct that differ only by spelling (typos) — NOT by PL_/number prefix.

    Prefix differences (PL_NumberCarSpace vs NumberCarSpace) are a separate,
    known pattern and are excluded here. This targets genuine spelling issues
    like ElectircalUpdatedYear vs ElectricalUpdatedYear.

    already_matched: set of ODM canonical names (lowercased) that already resolved
    to a Direct field via the multi-column join — these are skipped, they are
    not spelling problems.

    Per user instruction: do NOT auto-correct. Surface each pair for the user
    to confirm whether they are the same field. Output to a dedicated file.
    """
    from difflib import SequenceMatcher
    import re

    already_matched = already_matched or set()

    def similar(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def strip_prefix(f):
        # Remove PL_, PL, and leading number codes (F123_, 123_)
        s = re.sub(r'^PL_?', '', f)
        s = re.sub(r'^F?\d+_?', '', s)
        return s.lower().replace('[]', '')

    defaults = odm_df[odm_df['Rule Type'] == 'Default']
    odm_fields = sorted(set(f for f in defaults['Canonical'].unique()
                            if f and '/' not in f and f != 'nan'))
    direct_fields = sorted(set(direct_df['Canonical Name'].str.strip()) - {'', 'nan'})
    direct_exact = set(f.lower() for f in direct_fields)

    rows = []
    for of in odm_fields:
        if of.lower() in direct_exact:
            continue  # exact match, skip
        if of.lower() in already_matched:
            continue  # resolved via multi-column join, not a spelling issue
        best, best_score = None, 0
        for df in direct_fields:
            s = similar(of, df)
            if s > best_score:
                best_score, best = s, df
        if not (0.75 <= best_score < 1.0):
            continue
        of_core = strip_prefix(of)
        df_core = strip_prefix(best)
        # Never-merge: distinct fields that happen to look similar (per Bolt eng).
        NEVER_MERGE = [frozenset({'predateoccupied1', 'dateoccupied'}),
                       frozenset({'preeffectivedate1', 'effectivedate'})]
        if frozenset({of.lower().lstrip('f0123456789_'), best.lower()}) in NEVER_MERGE \
           or frozenset({of_core, df_core}) in NEVER_MERGE:
            continue
        # A 'pre' prefix (PreDateOccupied vs DateOccupied) changes the field's
        # meaning — do not treat as a spelling variant.
        if of_core.startswith('pre') ^ df_core.startswith('pre'):
            continue
        # Skip pure prefix-only differences (same core) — those are the known
        # PL_ duplicate pattern, handled elsewhere
        if of_core == df_core:
            continue
        # Only keep genuine spelling-level differences
        if similar(of_core, df_core) >= 0.80:
            rows.append({
                'ODM Field':        of,
                'Direct Field':     best,
                'Similarity':       round(best_score, 2),
                'ODM Core':         of_core,
                'Direct Core':      df_core,
                'Issue':            'POSSIBLE SPELLING MISMATCH — same field, different spelling?',
                'Action':           'CONFIRM WITH USER: is this the same field? Do not auto-correct.',
            })
    return pd.DataFrame(rows)


# ── Duplicate Field Detection ─────────────────────────────────────────────────

def find_duplicate_field_pairs(odm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect fields that exist twice under different names — a base field and a
    PL_-prefixed twin (e.g. NumberCarSpace + PL_NumberCarSpace).

    This is a data-integrity issue: the ODM has two separate PolicyData fields
    for what should be one field. Typically the non-PL field holds an OdmDefault
    (often a word value like "Two") while the PL_ field holds the real typed
    input (e.g. 2 from ConsumerInput). Confirmed via Policy Data Audit.

    These must be reviewed with product — they are NOT a value-format bug, they
    are duplicate fields that need consolidation. Surfaced in a dedicated
    Field_Duplication_Issues.csv, separate from the normal Review pile.
    """
    defaults = odm_df[odm_df['Rule Type'] == 'Default'].copy()
    fields = set(defaults['Canonical'].unique()) - {'', 'nan'}

    rows = []
    for f in sorted(fields):
        if f.startswith('PL_'):
            continue
        # Look for a PL_ twin: PL_<f> or PL_Fnnn_<f>
        twins = [o for o in fields
                 if o != f and o.startswith('PL_')
                 and (o == f'PL_{f}' or o.endswith(f'_{f}'))]
        for twin in twins:
            for name in [f, twin]:
                matches = defaults[defaults['Canonical'] == name]
                for _, r in matches.iterrows():
                    rows.append({
                        'Pair':          f'{f} / {twin}',
                        'Field Name':    name,
                        'UUID':          r.get('UUID', ''),
                        'Default Value': r.get('Default Value', ''),
                        'Flow':          r.get('Flow', ''),
                        'Page':          r.get('Page', ''),
                        'Issue':         'DUPLICATE FIELD — base field and PL_ twin both exist',
                        'Action':        'Review with product: consolidate to one field. '
                                         'Non-PL usually holds OdmDefault, PL_ holds real input.',
                    })
    return pd.DataFrame(rows)


# ── Gap Detection ─────────────────────────────────────────────────────────────

def find_direct_only_gaps(odm_canonicals: set, direct_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fields in Direct that have a Default Value specified but no ODM rule.
    These are defaults defined in the spec but missing from ODM — need to be
    written in RE from scratch.
    """
    has_direct_default = direct_df[
        direct_df['Default Value'].notna() &
        (direct_df['Default Value'].astype(str).str.strip() != '') &
        (direct_df['Default Value'].astype(str).str.strip() != 'nan')
    ]

    gaps = []
    for _, row in has_direct_default.iterrows():
        canonical = str(row.get('Canonical Name', '') or '').strip()
        if canonical and canonical not in odm_canonicals:
            gaps.append({
                'Field':         canonical,
                'Page':          row.get('Page', ''),
                'Flow':          row.get('Flow', ''),
                'LOBs':          row.get('LOBs', ''),
                'Control Type':  row.get('Control Type', ''),
                'Direct Default': row.get('Default Value', ''),
                'Gap Type':      'DIRECT-ONLY',
                'Note':          'Direct specifies a default value but no ODM rule exists — '
                                 'must be written in RE from scratch',
            })
    return pd.DataFrame(gaps)


# ── Main ──────────────────────────────────────────────────────────────────────

def load_mapping_decisions(output_dir: str, prefix: str) -> dict:
    """
    Load confirmed field-mapping decisions if the file exists.
    Returns {odm_field: direct_field} for SAME FIELD decisions only.
    DIFFERENT FIELD decisions are tracked separately to suppress spelling re-flagging.

    The decisions file is a persistent record of user confirmations — once a
    spelling/near-match pair is confirmed, it never needs re-asking.
    """
    path = os.path.join(output_dir, f"{prefix}_Field_Mapping_Decisions.csv")
    same, different = {}, set()
    if not os.path.exists(path):
        return {'same': same, 'different': different}
    try:
        dec = pd.read_csv(path, dtype=str).fillna('')
        for _, r in dec.iterrows():
            odm_f = r['ODM Field'].strip()
            dir_f = r['Direct Field'].strip()
            if 'SAME' in r['Decision'].upper():
                same[odm_f] = dir_f
            elif 'DIFFERENT' in r['Decision'].upper():
                different.add((odm_f, dir_f))
        print(f"Loaded mapping decisions: {len(same)} same-field, {len(different)} different-field")
    except Exception as e:
        print(f"Could not load decisions file: {e}")
    return {'same': same, 'different': different}


def run(odm_path: str, direct_path: str, output_dir: str, prefix: str,
        enum_norm_path: str = 'PGR_Enum_Label_Normalization.json'):
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nLoading ODM defaults: {odm_path}")
    odm_df = pd.read_csv(odm_path, dtype=str).fillna('')

    print(f"Loading Direct master: {direct_path}")
    direct_df = pd.read_csv(direct_path, dtype=str).fillna('')

    enum_map = load_enum_norm(enum_norm_path)
    print(f"Enum-label normalization: {len(enum_map)} field entries loaded"
          if enum_map else "Enum-label normalization: none loaded")

    # Load any confirmed mapping decisions from a prior session
    decisions = load_mapping_decisions(output_dir, prefix)

    # ── Prepare ODM: add canonical join key ───────────────────────────────────
    odm_df['Canonical'] = odm_df['Field Name'].apply(odm_field_to_canonical)

    # Apply confirmed SAME-FIELD decisions: remap ODM canonical to the Direct name
    # so the join succeeds (e.g. ElectircalUpdatedYear → ElectricalUpdatedYear)
    if decisions['same']:
        odm_df['Canonical'] = odm_df['Canonical'].replace(decisions['same'])

    # Only process Default rule type rows (skip Relevancy, Stage)
    defaults_only = odm_df[odm_df['Rule Type'] == 'Default'].copy()
    print(f"ODM default rules: {len(defaults_only)}")
    print(f"Direct fields:     {len(direct_df)}")

    # ── Build Direct lookup: multiple name columns → row ──────────────────────
    # A field may be named differently across columns. ODM's field name might
    # match any of: Canonical Name, Pre-fill Element (minus PolicyData. prefix),
    # GetQuote_DD, or Platform Field. We key the lookup on ALL of them so the
    # join succeeds regardless of which name ODM uses. Canonical Name wins as
    # the primary key when multiple columns are populated.
    NAME_COLS = ['Canonical Name', 'Pre-fill Element', 'GetQuote_DD', 'Platform Field']

    def clean_name(v):
        v = str(v or '').strip()
        v = re.sub(r'^PolicyData\.', '', v)   # Pre-fill Element uses dotted path
        v = re.sub(r'^PolicyData/', '', v)
        return v

    direct_lookup = {}       # any known name (lowercased) → row
    canonical_of = {}        # any known name (lowercased) → canonical name
    for _, row in direct_df.iterrows():
        cn = str(row.get('Canonical Name', '') or '').strip()
        if not cn or cn in ('', 'nan'):
            continue
        for col in NAME_COLS:
            val = clean_name(row.get(col, ''))
            if val and val not in ('', 'nan'):
                key = val.lower()
                if key not in direct_lookup:
                    direct_lookup[key] = row
                    canonical_of[key] = cn

    def lookup_direct(odm_field_canonical):
        """Find a Direct row by trying the ODM field name against all name columns."""
        key = str(odm_field_canonical or '').strip().lower()
        return direct_lookup.get(key)

    odm_canonicals = set(defaults_only['Canonical'].unique()) - {'', 'nan'}

    # ── Agent/Consumer divergence ─────────────────────────────────────────────
    print("\nChecking Agent/Consumer divergence...")
    diff_df = find_agent_consumer_diffs(defaults_only, enum_map)
    print(f"  Fields with Agent/Consumer default differences: {len(diff_df)}")

    print("\nChecking for duplicate field pairs (base vs PL_ twin)...")
    dup_df = find_duplicate_field_pairs(defaults_only)
    dup_pair_count = dup_df['Pair'].nunique() if not dup_df.empty else 0
    print(f"  Duplicate field pairs found: {dup_pair_count}")

    print("\nChecking for spelling mismatches (ODM vs Direct)...")
    # ODM canonicals that resolved to Direct via any name column — not spelling issues
    matched_odm_keys = {str(c).strip().lower() for c in odm_canonicals
                        if str(c).strip().lower() in direct_lookup}
    spell_df = find_spelling_mismatches(defaults_only, direct_df, already_matched=matched_odm_keys)
    # Suppress pairs already decided (same or different) in a prior session
    if not spell_df.empty and (decisions['same'] or decisions['different']):
        decided_odm = set(decisions['same'].keys()) | {o for o, d in decisions['different']}
        spell_df = spell_df[~spell_df['ODM Field'].isin(decided_odm)]
    print(f"  Possible spelling mismatches (undecided): {len(spell_df)}")

    # ── Classify each ODM default rule ────────────────────────────────────────
    print("\nClassifying rules...")
    system_rows, business_rows, review_rows, gap_rows = [], [], [], []

    for _, row in defaults_only.iterrows():
        canonical   = row['Canonical']
        direct_row  = lookup_direct(canonical)

        classification, reason, flags = classify_rule(row, direct_row)

        out_row = {
            'Page':                  row.get('Page', ''),
            'Field Name':            row.get('Field Name', ''),
            'Canonical':             canonical,
            'Rule Type':             row.get('Rule Type', ''),
            'UUID':                  row.get('UUID', ''),
            'Business Name':         row.get('Business Name', ''),
            'Flow':                  row.get('Flow', ''),
            'LOBs':                  row.get('LOBs', ''),
            'Claim Sources':         row.get('Claim Sources', ''),
            'Source Scope':          row.get('Source Scope', ''),
            'Other BA Flags':        row.get('Other BA Flags', ''),
            'Field Conditions':      row.get('Field Conditions', ''),
            'Simplified Conditions': row.get('Simplified Conditions', ''),
            'Default Value':         row.get('Default Value', ''),
            'Visible':               row.get('Visible', ''),
            # Enriched from Direct
            'Direct Control Type':   direct_row.get('Control Type', '') if direct_row is not None else 'NOT IN DIRECT',
            'Direct Display Rules':  direct_row.get('Display Rules', '') if direct_row is not None else '',
            'Direct Default Value':  direct_row.get('Default Value', '') if direct_row is not None else '',
            'Default Match (norm)':  (
                '(no direct)' if direct_row is None else
                'MATCH'  if norm_value(canonical, row.get('Default Value',''), enum_map) ==
                            norm_value(canonical, direct_row.get('Default Value',''), enum_map)
                         and norm_value(canonical, row.get('Default Value',''), enum_map) != '' else
                '(direct blank)' if norm_value(canonical, direct_row.get('Default Value',''), enum_map)=='' else
                'DIFFER'
            ),
            'Direct LOBs':           direct_row.get('LOBs', '')          if direct_row is not None else '',
            # Classification
            'Classification':        classification,
            'Classification Reason': reason,
            'Flags':                 ' | '.join(flags) if flags else '',
            'Needs Review':          row.get('Needs Review', ''),
        }

        # Route to gap report for ODM-only
        if any('ODM-ONLY' in f for f in flags):
            gap_row = {
                'Field':     canonical,
                'Page':      row.get('Page', ''),
                'Flow':      row.get('Flow', ''),
                'UUID':      row.get('UUID', ''),
                'Gap Type':  'ODM-ONLY',
                'Note':      'ODM has a default rule but field not found in Direct — verify in scope',
                'ODM Default Value': row.get('Default Value', ''),
                'Direct Default Value': '',
            }
            gap_rows.append(gap_row)

        if classification == 'System':
            system_rows.append(out_row)
        elif classification == 'Business':
            business_rows.append(out_row)
        else:
            review_rows.append(out_row)

    # ── Direct-only gaps ──────────────────────────────────────────────────────
    # A Direct field is only a gap if NO ODM field resolves to its canonical name
    # via ANY name column. Build the set of Direct canonicals that ODM matched.
    matched_canonicals = set()
    for c in odm_canonicals:
        key = str(c).strip().lower()
        if key in canonical_of:
            matched_canonicals.add(canonical_of[key])
    direct_gap_df = find_direct_only_gaps(matched_canonicals, direct_df)
    for _, row in direct_gap_df.iterrows():
        gap_rows.append(row.to_dict())

    # ── Write outputs ─────────────────────────────────────────────────────────
    def write(rows, name):
        if rows:
            df = pd.DataFrame(rows)
            path = os.path.join(output_dir, f"{prefix}_{name}.csv")
            df.to_csv(path, index=False, encoding='utf-8-sig')
            print(f"  {os.path.basename(path)}  ({len(df)} rows)")
            return df
        else:
            print(f"  {prefix}_{name}.csv  (empty — not written)")
            return pd.DataFrame()

    print(f"\nWriting outputs to: {output_dir}")
    write(system_rows,   'System_Defaults')
    write(business_rows, 'Business_Defaults')
    write(review_rows,   'Review_Defaults')
    write(gap_rows,      'Gaps_Report')

    if not diff_df.empty:
        path = os.path.join(output_dir, f"{prefix}_Agent_Consumer_Diff.csv")
        diff_df.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"  {os.path.basename(path)}  ({len(diff_df)} rows)")
    else:
        print(f"  {prefix}_Agent_Consumer_Diff.csv  (empty — not written)")

    # Dedicated file for duplicate field issues — separate from the Review pile
    # because these are important data-integrity issues for product review.
    if not dup_df.empty:
        path = os.path.join(output_dir, f"{prefix}_Field_Duplication_Issues.csv")
        dup_df.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"  {os.path.basename(path)}  ({dup_df['Pair'].nunique()} pairs, {len(dup_df)} rows) ⚠ REVIEW WITH PRODUCT")
    else:
        print(f"  {prefix}_Field_Duplication_Issues.csv  (empty — not written)")

    # Dedicated file for spelling mismatches — user confirms if same field.
    if not spell_df.empty:
        path = os.path.join(output_dir, f"{prefix}_Spelling_Mismatches.csv")
        spell_df.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"  {os.path.basename(path)}  ({len(spell_df)} pairs) ⚠ CONFIRM WITH USER")
    else:
        print(f"  {prefix}_Spelling_Mismatches.csv  (empty — not written)")

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(defaults_only)
    print(f"""
{'='*60}
Classification summary
{'='*60}
Total ODM default rules:       {total}
  → System:                    {len(system_rows)}
  → Business:                  {len(business_rows)}
  → Review (needs decision):   {len(review_rows)}

Gaps:
  ODM-only (not in Direct):    {sum(1 for g in gap_rows if g.get('Gap Type') == 'ODM-ONLY')}
  Direct-only (no ODM rule):   {len(direct_gap_df)}

Agent/Consumer differences:    {len(diff_df)}
""")

    if review_rows:
        review_df = pd.DataFrame(review_rows)
        review_df['_cat'] = review_df['Classification Reason'].str.split('—').str[0].str.strip()
        print("REVIEW ITEMS by category (resolve before proceeding):")
        for cat, n in review_df['_cat'].value_counts().items():
            print(f"  {n:4d}  {cat}")
        print(f"\n  Full detail in {prefix}_Review_Defaults.csv")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Classify ODM defaults as System (RE) or Business (SQL)')
    parser.add_argument('--odm',    required=True, help='Path to {prefix}_Defaults.csv')
    parser.add_argument('--direct', required=True, help='Path to Progressive_Direct_Master.csv')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--prefix', default='PGR',  help='Filename prefix (default: PGR)')
    parser.add_argument('--enum-norm', default='PGR_Enum_Label_Normalization.json',
                        help='Path to enum-label normalization JSON')
    args = parser.parse_args()

    run(args.odm, args.direct, args.output, args.prefix, args.enum_norm)
