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

# Direct Control Type values that classify as System default
SYSTEM_CONTROL_TYPES = {
    'checkbox', 'check box',
    'stepper', 'numeric stepper',
}

# Direct Control Type values that are Radio — flag if ODM has a default for these
RADIO_CONTROL_TYPES = {
    'radio', 'radio button', 'radiobutton',
    'segmented control', 'segmentedcontrol', 'segmented controls',
}


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
    """Lowercase and strip control type for comparison."""
    return str(ct).strip().lower() if ct and str(ct).strip() not in ('', 'nan') else ''


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

    # ── Rule 1: Cleaning logic — empty string default ─────────────────────────
    if default_val == '""' or default_val == "''":
        return 'System', 'Cleaning logic — empty string reset (parent/child)', flags
    # Also catch literally empty after stripping quotes
    stripped_val = default_val.strip('"').strip("'")
    if stripped_val == '' and default_val != '':
        return 'System', 'Cleaning logic — empty string reset (parent/child)', flags

    if direct_row is None:
        # No Direct match — cannot fully classify
        flags.append('ODM-ONLY: field not found in Direct — verify field is in scope')
        return 'Review', 'No Direct match — control type unknown, cannot classify', flags

    direct_ct   = normalize_ct(direct_row.get('Control Type', ''))
    display_rules = str(direct_row.get('Display Rules', '') or '').strip().lower()

    # ── Rule 2/3: Checkbox or Stepper in Direct → System ─────────────────────
    if direct_ct in SYSTEM_CONTROL_TYPES:
        ct_label = direct_row.get('Control Type', direct_ct)
        # Check if ODM thinks it's a checkbox too, or something else
        if odm_ct and odm_ct != direct_ct and odm_ct not in ('', 'nan'):
            flags.append(
                f'CONTROL-TYPE-CONFLICT: ODM={odm_ct}, Direct={direct_ct} — Direct wins per convention, verify')
        return 'System', f'Control type is {ct_label} (Direct)', flags

    # ── Special: Radio in Direct → flag, do not classify yet ─────────────────
    if direct_ct in RADIO_CONTROL_TYPES:
        flags.append(
            f'RADIO-CONFLICT: Direct says Radio/Segmented, ODM has a default value '
            f'"{default_val}" — Radio questions are not checkboxes. '
            f'Please decide: should this default exist? If yes, what classification?')
        return 'Review', f'Radio question in Direct with ODM default — needs decision', flags

    # ── Rule 4: Hidden field → Business ──────────────────────────────────────
    if 'hidden' in display_rules:
        return 'Business', 'Hidden field (Display Rules contains "hidden")', flags

    # ── Unclear display rules that might mean hidden ──────────────────────────
    MAYBE_HIDDEN_PATTERNS = ['not visible', 'not displayed', 'never shown', 'not shown']
    for pattern in MAYBE_HIDDEN_PATTERNS:
        if pattern in display_rules:
            flags.append(
                f'POSSIBLE-HIDDEN: Display Rules contains "{pattern}" — '
                f'verify if this should be classified as hidden/Business')
            return 'Review', f'Display Rules may indicate hidden field — verify', flags

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

def find_agent_consumer_diffs(odm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Find fields where Agent and Consumer have different default values.
    Returns a DataFrame of diverging fields with both values shown.
    """
    # Only look at rows with actual default values
    has_default = odm_df[odm_df['Default Value'].notna() &
                         (odm_df['Default Value'].astype(str).str.strip() != '')]

    diffs = []
    fields = has_default['Canonical'].unique()

    for field in fields:
        rows = has_default[has_default['Canonical'] == field]
        agent_rows    = rows[rows['Flow'].isin(['Agent', 'Both'])]
        consumer_rows = rows[rows['Flow'].isin(['Consumer', 'Both'])]

        agent_vals    = set(agent_rows['Default Value'].astype(str).str.strip().unique())
        consumer_vals = set(consumer_rows['Default Value'].astype(str).str.strip().unique())

        # Remove empty
        agent_vals    = {v for v in agent_vals    if v not in ('', 'nan')}
        consumer_vals = {v for v in consumer_vals if v not in ('', 'nan')}

        if not agent_vals or not consumer_vals:
            continue

        if agent_vals != consumer_vals:
            diffs.append({
                'Field':          field,
                'Agent Default':  ', '.join(sorted(agent_vals)),
                'Consumer Default': ', '.join(sorted(consumer_vals)),
                'Note': 'Same field, different defaults per flow — verify both are intentional',
            })

    return pd.DataFrame(diffs)


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

def run(odm_path: str, direct_path: str, output_dir: str, prefix: str):
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nLoading ODM defaults: {odm_path}")
    odm_df = pd.read_csv(odm_path, dtype=str).fillna('')

    print(f"Loading Direct master: {direct_path}")
    direct_df = pd.read_csv(direct_path, dtype=str).fillna('')

    # ── Prepare ODM: add canonical join key ───────────────────────────────────
    odm_df['Canonical'] = odm_df['Field Name'].apply(odm_field_to_canonical)

    # Only process Default rule type rows (skip Relevancy, Stage)
    defaults_only = odm_df[odm_df['Rule Type'] == 'Default'].copy()
    print(f"ODM default rules: {len(defaults_only)}")
    print(f"Direct fields:     {len(direct_df)}")

    # ── Build Direct lookup: canonical → rows (can be multiple flows) ─────────
    # Group by Canonical Name — take first row per canonical for metadata lookup
    direct_lookup = {}
    for _, row in direct_df.iterrows():
        cn = str(row.get('Canonical Name', '') or '').strip()
        if cn and cn not in ('', 'nan'):
            if cn not in direct_lookup:
                direct_lookup[cn] = row

    odm_canonicals = set(defaults_only['Canonical'].unique()) - {'', 'nan'}

    # ── Agent/Consumer divergence ─────────────────────────────────────────────
    print("\nChecking Agent/Consumer divergence...")
    diff_df = find_agent_consumer_diffs(defaults_only)
    print(f"  Fields with Agent/Consumer default differences: {len(diff_df)}")

    # ── Classify each ODM default rule ────────────────────────────────────────
    print("\nClassifying rules...")
    system_rows, business_rows, review_rows, gap_rows = [], [], [], []

    for _, row in defaults_only.iterrows():
        canonical   = row['Canonical']
        direct_row  = direct_lookup.get(canonical)

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
            # Enriched from Direct
            'Direct Control Type':   direct_row.get('Control Type', '') if direct_row is not None else 'NOT IN DIRECT',
            'Direct Display Rules':  direct_row.get('Display Rules', '') if direct_row is not None else '',
            'Direct Default Value':  direct_row.get('Default Value', '') if direct_row is not None else '',
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
    direct_gap_df = find_direct_only_gaps(odm_canonicals, direct_df)
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
        print("REVIEW ITEMS — resolve before proceeding:")
        review_df = pd.DataFrame(review_rows)
        for _, r in review_df.iterrows():
            print(f"  [{r['Flow']}] {r['Field Name']} — {r['Classification Reason']}")
            if r['Flags']:
                for flag in r['Flags'].split(' | '):
                    print(f"    ⚠ {flag}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Classify ODM defaults as System (RE) or Business (SQL)')
    parser.add_argument('--odm',    required=True, help='Path to {prefix}_Defaults.csv')
    parser.add_argument('--direct', required=True, help='Path to Progressive_Direct_Master.csv')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--prefix', default='PGR',  help='Filename prefix (default: PGR)')
    args = parser.parse_args()

    run(args.odm, args.direct, args.output, args.prefix)
