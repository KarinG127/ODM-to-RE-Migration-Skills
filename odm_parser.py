#!/usr/bin/env python3
"""
ODM .m File Parser — Standalone CLI Script
Parses IBM ODM rule files into structured CSV output.

Usage:
    python3 odm_parser.py --config tenant_config.json --input /path/to/odm/ --output /path/to/output/ --prefix ODM_Full

Requires: pandas (pip install pandas)

This script is fully generic — all tenant-specific logic lives in the config JSON.
To use with a new tenant, create a new config JSON (see README for schema).
"""

import re, os, json, argparse
import pandas as pd
from typing import Optional

CONDITION_SIMPLIFICATIONS = [
    (r'Lobses contain (\w+)',        r'LOB = \1'),
    (r'Lobses do not contain (\w+)', r'LOB != \1'),
    (r'is one of \{([^}]+)\}',       lambda m: 'in [' + ', '.join(v.strip().strip('"') for v in m.group(1).split(',')) + ']'),
    (r'(\w+)\s+\.\s+(\w+)',          r'\1.\2'),
    (r'is not unknown',              'is known'),
    (r'all of the following conditions are true\s*:', ''),
    (r'one of the following conditions is true\s*:',  ''),
    (r'\s*-\s*\d+\s+is\s+more\s+than\s+-?\d+',       ''),
    (r'  +', ' '),
]

def simplify_conditions(conditions: str) -> str:
    if not conditions or conditions == 'true':
        return conditions
    result = conditions
    for pattern, replacement in CONDITION_SIMPLIFICATIONS:
        result = re.sub(pattern, replacement, result)
    result = re.sub(r'^\s*[\-\:]\s*', '', result).strip()
    result = re.sub(r'\s*,\s*$', '', result).strip()
    return result if result else conditions


# ── File Reading ──────────────────────────────────────────────────────────────

def read_odm_file(filepath: str) -> str:
    """
    IBM ODM generates UTF-16 LE encoded files on Windows. Falls back to UTF-8.
    Validates decoded content by checking for known ODM markers ('package' or
    'ORIGINAL_BAL') to avoid false positives from BOM-like byte sequences in
    UTF-8 files.
    """
    with open(filepath, 'rb') as f:
        raw = f.read()
    for enc in ['utf-16', 'utf-16-le', 'utf-8']:
        try:
            content = raw.decode(enc)
            if len(content) > 50 and ('package' in content or 'ORIGINAL_BAL' in content):
                return content
        except Exception:
            continue
    raise ValueError(f"Could not decode: {filepath}")


# ── Skip-Flag Check ───────────────────────────────────────────────────────────

def should_skip_file(content: str, config: dict) -> bool:
    """
    Return True if this entire rule file should be excluded from output.
    Reasons:
      - fieldId targets a SectionClaim (not a real policy data field)
      - fieldId targets a CustomField marked as 'skip' in config
      - File contains a skip_flag (e.g. ViewMode, DataDictionary, dead A/B tests)
      - ORIGINAL_BAL contains 'and false' — entire rule is dead
    For skip_flags with always_on=True: only skip when IS ENABLED=false
    (that branch never fires — the IS ENABLED=true branch is kept).
    """
    if 'SectionClaim/' in content:
        return True

    # Check CustomFields routing from config
    fm = re.search(r'fieldId\s*=\s*"PolicyData/([^"]+)"', content)
    if fm and fm.group(1).startswith('CustomFields/'):
        field_short = fm.group(1).split('/')[-1]
        routing = config.get('review_later', {}).get('custom_fields', {}).get(field_short)
        if routing == 'skip':
            return True

    skip_cfg = config.get('skip_flags', {})
    for m in re.finditer(r'isInFeature\("([^"]+)"', content):
        flag_name = m.group(1).strip()
        if flag_name in skip_cfg:
            sf = skip_cfg[flag_name]
            if sf.get('always_on') is True:
                enabled_m = re.search(
                    rf'THE FEATURE "{re.escape(flag_name)}" IS ENABLED IN features is (true|false)', content)
                if enabled_m and enabled_m.group(1) == 'false':
                    return True
            else:
                return True

    bal = re.search(r'<ORIGINAL_BAL(.+?)ORIGINAL_BAL>', content, re.DOTALL)
    if bal and re.search(r'\band\s+false\s*\)', bal.group(1)):
        return True

    return False


# ── Flag Extraction ───────────────────────────────────────────────────────────

def extract_flags(content: str, config: dict) -> tuple:
    """
    Extract and classify all feature flags.
    Returns: (flow, sources, ba_flags_raw, unknown_flags)

    Firing logic:
      IS ENABLED = true  → fires when flag is ON
      IS ENABLED = false → fires when flag is OFF
    always_on=True  → only IS ENABLED=true branch fires
    always_on=False → only IS ENABLED=false branch fires
    always_on=None  → source-dependent, evaluate per condition
    """
    claim_cfg  = config.get('claim_flags', {})
    ba_cfg     = config.get('business_flags', {})
    interp_cfg = config.get('source_flags', {}).get('interpretation', {})

    flow = 'Both'
    sources, ba_flags_raw, unknown = [], [], []

    for m in re.finditer(r'isInFeature\("([^"]+)"', content):
        flag = m.group(1).strip()

        if flag.startswith('Claim:'):
            if flag in claim_cfg:
                c = claim_cfg[flag]
                if c.get('category') == 'section':
                    continue
                if c['category'] == 'flow':
                    flow = c['value']
                else:
                    sources.append(c['value'])
            else:
                unknown.append(flag)

        elif flag.startswith('ba_'):
            base = (flag[:-5] if flag.endswith('_True') else
                    (flag[:-6] if flag.endswith('_False') else flag)).strip()
            enabled_m = re.search(
                rf'THE FEATURE "{re.escape(flag)}" IS ENABLED IN features is (true|false)', content)
            condition_result = enabled_m.group(1) if enabled_m else 'unknown'
            known = ba_cfg.get(base, {})

            interp_key = f"{base}={condition_result}"
            interpretation = interp_cfg.get(interp_key, '')

            always_on = known.get('always_on')
            if always_on is True:
                fires = (condition_result == 'true')
            elif always_on is False:
                fires = (condition_result == 'false')
            else:
                fires = None

            ba_flags_raw.append({
                'flag_full':        flag,
                'base':             base,
                'condition_result': condition_result,
                'classification':   known.get('classification', 'UNRESOLVED'),
                'always_on':        always_on,
                'fires':            fires,
                'interpretation':   interpretation,
                'reason':           known.get('reason', '')
            })

        else:
            skip_cfg = config.get('skip_flags', {})
            if flag in skip_cfg:
                continue
            unknown.append(flag)

    return flow, sources, ba_flags_raw, unknown


# ── LOB Extraction ────────────────────────────────────────────────────────────

def extract_lobs(content: str, config: dict) -> tuple:
    lob_map = config.get('lob_map', {})
    includes, excludes = [], []
    for key, code in lob_map.items():
        if f'Lob.{key} !in quoteData.Lobs' in content or f'do not contain {key}' in content:
            excludes.append(code)
        elif f'Lob.{key} in quoteData.Lobs' in content or f'contain {key}' in content:
            includes.append(code)
    return list(set(includes)), list(set(excludes))


# ── Attribute Extraction ──────────────────────────────────────────────────────

def extract_attributes(content: str) -> dict:
    attrs = {}
    m = re.search(r'InterviewAttributeType\.Sequence,\s*java\.lang\.Integer\.valueOf\(\(int\)\s*(\d+)', content)
    if m: attrs['sequence'] = m.group(1)
    m = re.search(r'InterviewAttributeType\.Title,\s*"([^"]+)"', content)
    if m: attrs['title'] = m.group(1)
    m = re.search(r'InterviewAttributeType\.FieldControl,\s*\S+\.(\w+)\s*\)', content)
    if m: attrs['control_type'] = m.group(1)
    m = re.search(r'InterviewAttributeType\.Mandatory,\s*(true|false)', content)
    if m: attrs['mandatory'] = m.group(1)
    m = re.search(r'InterviewAttributeType\.Relevant,\s*(true|false)', content)
    if m: attrs['relevant'] = m.group(1)
    m = re.search(r'InterviewAttributeType\.Visible,\s*(true|false)', content)
    if m: attrs['visible'] = m.group(1)
    if 'InterviewAttributeType.Stage' in content:
        attrs['stage_set'] = True
    m = re.search(r'INTERVIEW ATTRIBUTE= DefaultValue VALUE= ([^\n;*]+)', content)
    if m:
        raw_val = m.group(1).strip()
        attrs['default_value'] = _parse_default_value(raw_val)
    return attrs


# Ordered table of (test, output) for default value parsing.
# Each entry is (callable(raw_val) -> bool, callable(raw_val) -> str).
# First match wins.
def _parse_default_value(raw: str) -> str:
    """Classify a raw ODM DefaultValue string into a human-readable form."""
    # Field reference helper
    def field_ref(r):
        m = re.search(r"'the policy data'\s*\.\s*(\w+)", r)
        return m.group(1) if m else None

    # Each entry: (test, output_string_or_callable)
    # Tests and outputs are kept simple — no regex reuse across test/output boundary.
    if 'YearsAtAddress' in raw and '01/01/' in raw:
        return "01/01/(today's year - YearsAtAddress)"
    if 'YearsAtAddress' in raw and '1.1.' in raw:
        return "1.1.(today's year - YearsAtAddress)"
    if 'YearsAtAddress' in raw:
        return "today's year - YearsAtAddress"

    m = re.search(r'AS NUMERIC\s*\)\s*-\s*(\d+)', raw)
    if ('FORMAT STRING' in raw or 'TODAY' in raw) and m:
        return f"today's year - {m.group(1)}"

    if 'DATE_YYYY_MM_DD' in raw and 'PurchaseDate' in raw:
        return "PurchaseDate as YYYY-MM-DD"
    if 'PurchaseDate' in raw and '15' in raw:
        return "PurchaseDate month/15/year"

    if 'PropertyAddress' in raw and "'the policy data'" in raw:
        m = re.search(r'PropertyAddress\s*\.\s*(\w+)', raw)
        return f"PropertyAddress.{m.group(1)}" if m else raw

    if "'the policy data'" in raw:
        ref = field_ref(raw)
        return ref if ref else raw

    if 'FORMAT STRING' in raw or 'TODAY' in raw:
        ref = field_ref(raw)
        m = re.search(r'Format\.\s*(\w+)', raw)
        return f"{ref} formatted as {m.group(1)}" if ref and m else "[Calculated date — see UUID]"

    return raw.strip('"').strip("'")


# ── Condition Extraction ──────────────────────────────────────────────────────

def extract_conditions(content: str) -> str:
    """
    Extract field conditions verbatim from ORIGINAL_BAL comment block.
    Returns 'true' when no field conditions exist.

    Two-pass approach:
      Pass 1 — strip comment markers and isolate the raw condition block
               by dropping the known preamble (feature flags, stage setup)
               and stopping at 'then'.
      Pass 2 — drop ODM boilerplate lines (bare true, SET VAR, etc.)
               and join what remains.
    """
    bal = re.search(r'<ORIGINAL_BAL(.+?)ORIGINAL_BAL>', content, re.DOTALL)
    if not bal:
        return 'true'

    # Pass 1 — clean comment markers, cut at 'then', drop preamble sections.
    # Preamble = feature-flag block + definitions/set/if/stage-gate block.
    # Both are stripped by the same set of line-prefix checks before we flip
    # 'in_conditions'. Once flipped it stays True for the rest of the block.
    PREAMBLE_PATTERNS = (
        re.compile(r'isInFeature\('),
        re.compile(r'IS ENABLED IN features is'),
        re.compile(r'^definitions\b'),
        re.compile(r"^set\s+'currentStage'"),
        re.compile(r'^if\s*$'),
        re.compile(r'^(all|one)\s+of\s+the\s+following'),
        re.compile(r'currentStage\s+is\b'),
    )
    raw_lines = []
    in_conditions = False
    for line in bal.group(1).split('\n'):
        clean = re.sub(r'^\s*\*[\s\t]*', '', line).strip()
        clean = re.sub(r'^\\t+', '', clean).strip()
        if not clean:
            continue
        if re.search(r'\bthen\b', clean):
            break
        if clean in (', ,', ',  ,') or clean.startswith('print ') or clean.startswith("'the interview"):
            break
        if not in_conditions:
            if any(p.search(clean) for p in PREAMBLE_PATTERNS):
                continue
            in_conditions = True
        raw_lines.append(clean)

    # Pass 2 — drop standalone boilerplate lines, join remainder.
    BOILERPLATE = (
        re.compile(r'^-?\s*true\s*$'),
        re.compile(r'^(and|or)\s+true\s*$'),
        re.compile(r'^SET VAR'),
    )
    cond_lines = [l for l in raw_lines if not any(p.match(l) for p in BOILERPLATE)]

    if not cond_lines:
        return 'true'

    result = ' '.join(cond_lines)
    result = re.sub(r"'the policy data'\s*\.\s*", '', result)
    result = re.sub(r'\s*,\s*,.*$', '', result).strip()
    result = re.sub(r'^(and|or)\s+', '', result).strip()
    return result if result else 'true'


# ── Rule Type Detection ───────────────────────────────────────────────────────

def detect_rule_type(attrs: dict, field_name: Optional[str]) -> str:
    if attrs.get('default_value') is not None:              return 'Default'
    if attrs.get('stage_set') and not field_name:           return 'Stage'
    if attrs.get('relevant'):                               return 'Relevancy'
    if attrs.get('mandatory') or attrs.get('control_type'): return 'Relevancy'
    if attrs.get('stage_set'):                              return 'Stage'
    if not field_name:                                      return 'Stage'
    return 'Stage'


# ── Review Later Routing ──────────────────────────────────────────────────────

def get_review_reason(r: dict, content: str, config: dict) -> str:
    """
    Determine if a rule should go to Review_Later CSV instead of main Rules CSV.
    All routing is driven by the config's review_later section.
    Returns a reason string, or '' if the rule belongs in main output.
    """
    rl = config.get('review_later', {})

    # Prefill rules without a default value
    prefill_key = rl.get('prefill_key', '')
    if prefill_key and re.search(rf'getByKey\s*\(\s*"{re.escape(prefill_key)}"', content):
        if r.get('default_value') is None:
            return f'Prefill ({prefill_key}) — no default value, review separately'

    # Pages that always go to Review Later
    for page in rl.get('pages', []):
        if r.get('page') == page:
            return f'{page} — rules for this page, review separately'

    # CustomFields routing
    if r.get('field_name') and r['field_name'].startswith('CustomFields/'):
        field_short = r['field_name'].split('/')[-1]
        routing = rl.get('custom_fields', {}).get(field_short)
        if routing == 'review_later':
            return f'CustomFields — relevancy only, no default ({field_short})'
        # Unknown CustomField not in config — will be caught as unresolved

    return ''


# ── Main Single-File Parser ───────────────────────────────────────────────────

def parse_odm_file(filepath: str, config: dict, source_flags: set) -> Optional[dict]:
    content = read_odm_file(filepath)

    if should_skip_file(content, config):
        return None

    r = {}
    r['uuid'] = os.path.basename(filepath).replace('.m', '')

    pkg = re.search(r'ilog\.rules\.package_name\s*=\s*"([^"]+)"', content)
    r['page'] = pkg.group(1).split('.')[-1] if pkg else None
    sm = re.search(r'evaluate\s*\(currentStage\s*:\s*\("([^"]+)"\)\)', content)
    if sm: r['page'] = sm.group(1)

    fm = re.search(r'fieldId\s*=\s*"PolicyData/([^"]+)"', content)
    r['field_name'] = fm.group(1) if fm else None

    bm = re.search(r'ilog\.rules\.business_name\s*=\s*"([^"]+)"', content)
    r['business_name'] = bm.group(1) if bm else None

    r['flow'], r['sources'], r['ba_flags_raw'], r['unknown_flags'] = extract_flags(content, config)
    r['lob_includes'], r['lob_excludes'] = extract_lobs(content, config)

    attrs = extract_attributes(content)
    r.update(attrs)

    r['conditions'] = extract_conditions(content)
    r['simplified_conditions'] = simplify_conditions(r['conditions'])
    r['rule_type'] = detect_rule_type(attrs, r['field_name'])

    # Skip rule if any non-source ba_ flag branch is INACTIVE
    for f in r['ba_flags_raw']:
        if f['base'] not in source_flags and f.get('fires') is False:
            return None

    # Tag review_reason — all routing driven by config
    r['review_reason'] = get_review_reason(r, content, config)

    # Flag unknown CustomFields not in config
    if r.get('field_name') and r['field_name'].startswith('CustomFields/'):
        field_short = r['field_name'].split('/')[-1]
        known_custom = config.get('review_later', {}).get('custom_fields', {})
        if field_short not in known_custom:
            r['unknown_flags'] = r.get('unknown_flags', []) + [
                f"CustomFields/{field_short} — unknown custom field, needs classification"]

    unresolved = [f for f in r['ba_flags_raw'] if f['classification'] == 'UNRESOLVED']
    r['needs_review'] = bool(r['unknown_flags'] or unresolved)
    return r


# ── Row Builders ──────────────────────────────────────────────────────────────

def build_row(r: dict, source_flags: set) -> dict:
    lob_incl = ', '.join(r.get('lob_includes', []))
    lob_excl = ', '.join(r.get('lob_excludes', []))
    lob_str  = lob_incl or (f'All except {lob_excl}' if lob_excl else 'All LOBs')

    source_raw_parts, source_interp_parts, other_flag_parts = [], [], []

    for f in r.get('ba_flags_raw', []):
        raw_str = f"{f['flag_full']} IS ENABLED = {f['condition_result']}"
        if f['base'] in source_flags:
            source_raw_parts.append(raw_str)
            if f.get('interpretation'):
                source_interp_parts.append(f['interpretation'])
        else:
            fires = f.get('fires')
            status = ('ACTIVE' if fires is True else
                      ('INACTIVE' if fires is False else 'SOURCE-DEPENDENT'))
            other_flag_parts.append(f"{raw_str} -> {f['classification']} {status}")

    return {
        'Page':                  r.get('page', ''),
        'Field Name':            r.get('field_name') or '(Stage-only rule)',
        'Rule Type':             r.get('rule_type', ''),
        'UUID':                  r.get('uuid', ''),
        'Business Name':         r.get('business_name', ''),
        'Flow':                  r.get('flow', 'Both'),
        'Claim Sources':         ', '.join(r.get('sources', [])),
        'LOBs':                  lob_str,
        'Source Flag (Raw)':     ' & '.join(source_raw_parts),
        'Source Scope':          ' & '.join(source_interp_parts),
        'Other BA Flags':        ' & '.join(other_flag_parts),
        'Field Conditions':      r.get('conditions', ''),
        'Simplified Conditions': r.get('simplified_conditions', ''),
        'Default Value':         r.get('default_value', ''),
        'Title':                 r.get('title', ''),
        'Control Type':          r.get('control_type', ''),
        'Mandatory':             r.get('mandatory', ''),
        'Relevant':              r.get('relevant', ''),
        'Sequence':              r.get('sequence', ''),
        'Needs Review':          'YES' if r.get('needs_review') else 'NO',
        'Unknown Flags':         ', '.join(r.get('unknown_flags', [])),
        'Review Reason':         r.get('review_reason', ''),
    }

def build_stage_row(r: dict) -> dict:
    flags_raw = r.get('ba_flags_raw', [])
    has_dead  = any(f['classification'] in ('CLEANUP', 'SKIP') for f in flags_raw)
    if has_dead:
        dead_flags = ', '.join(set(
            f['base'] for f in flags_raw if f['classification'] in ('CLEANUP', 'SKIP')))
        status = f'DEAD - {dead_flags}'
    elif not flags_raw:
        status = 'CLEAN - no feature flags'
    else:
        status = 'REVIEW'
    all_flags_raw = ' & '.join([
        f"{f['flag_full']} IS ENABLED = {f['condition_result']} [fires={f.get('fires')}]"
        for f in flags_raw
    ]) or '(none)'
    return {
        'UUID':                r.get('uuid', ''),
        'Business Name':       r.get('business_name', '(unknown)'),
        'Status':              status,
        'Flow':                r.get('flow', 'Both'),
        'Claim Sources':       ', '.join(r.get('sources', [])),
        'Feature Flags (Raw)': all_flags_raw,
        'Field Conditions':    r.get('conditions', '') or '(none)',
        'Review Notes':        '',
    }


# ── CSV Writer ────────────────────────────────────────────────────────────────

def write_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False, encoding='utf-8-sig')
    print(f"  {os.path.basename(path)}")


# ── Output Building ───────────────────────────────────────────────────────────

def _build_dataframes(records: list, source_flags: set, config: dict) -> dict:
    """Build all output DataFrames from parsed records. Returns a named dict."""
    main_records   = [r for r in records if not r.get('review_reason')]
    review_records = [r for r in records if r.get('review_reason')]

    stage_rows = [build_stage_row(r) for r in main_records
                  if r.get('rule_type') == 'Stage' and r.get('field_name')]

    unresolved = []
    for r in records:
        for f in r.get('unknown_flags', []):
            unresolved.append({'flag': f, 'type': 'unknown',
                               'field': r.get('field_name'), 'uuid': r.get('uuid')})
        for f in r.get('ba_flags_raw', []):
            if f['classification'] == 'UNRESOLVED':
                unresolved.append({'flag': f['base'], 'type': 'ba_unresolved',
                                   'field': r.get('field_name'), 'uuid': r.get('uuid')})

    active, retired = [], []
    for base, info in config.get('business_flags', {}).items():
        row = {'Flag': base, 'Classification': info['classification'],
               'Always ON': str(info.get('always_on', 'N/A')), 'Notes': info.get('reason', '')}
        (retired if info['classification'] in ('CLEANUP', 'SKIP') else active).append(row)

    return {
        'main':       pd.DataFrame([build_row(r, source_flags) for r in main_records]),
        'review':     pd.DataFrame([build_row(r, source_flags) for r in review_records]),
        'stage':      pd.DataFrame(stage_rows).sort_values('Status') if stage_rows else pd.DataFrame(),
        'unresolved': pd.DataFrame(unresolved).drop_duplicates(subset=['flag']) if unresolved else pd.DataFrame(),
        'active':     pd.DataFrame(active)  if active  else pd.DataFrame(),
        'retired':    pd.DataFrame(retired) if retired else pd.DataFrame(),
        '_counts':    {'main': len(main_records), 'review': len(review_records)},
    }


def _write_outputs(dfs: dict, output_dir: str, prefix: str):
    """Write all DataFrames to CSV. Skips empty files except main Rules."""
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nWriting CSVs to: {output_dir}")

    def write_if_nonempty(df, name):
        if not df.empty:
            write_csv(df, os.path.join(output_dir, f"{prefix}_{name}.csv"))

    write_csv(dfs['main'],               os.path.join(output_dir, f"{prefix}_Rules.csv"))
    write_if_nonempty(dfs['review'],     'Review_Later')
    write_if_nonempty(dfs['stage'],      'Stage_Rules_Review')
    write_if_nonempty(dfs['active'],     'Active_Flags')
    write_if_nonempty(dfs['retired'],    'Retired_Flags')
    write_if_nonempty(dfs['unresolved'], 'Unresolved_Flags')


# ── Batch Processing ──────────────────────────────────────────────────────────

def parse_all(root_dir: str, config: dict, output_dir: str, prefix: str = 'ODM'):
    source_flags = set(config.get('source_flags', {}).get('identity_flags', []))
    records, errors, skipped = [], [], 0

    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not fname.endswith('.m'):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                r = parse_odm_file(fpath, config, source_flags)
                if r is None:
                    skipped += 1
                else:
                    records.append(r)
            except Exception as e:
                errors.append({'file': fname, 'error': str(e)})

    dfs = _build_dataframes(records, source_flags, config)
    df_errors = pd.DataFrame(errors) if errors else pd.DataFrame()

    _write_outputs(dfs, output_dir, prefix)
    if not df_errors.empty:
        write_csv(df_errors, os.path.join(output_dir, f"{prefix}_Parse_Errors.csv"))

    needs_review_count = len(dfs['main'][dfs['main']['Needs Review'] == 'YES']) if not dfs['main'].empty else 0
    print(f"\nParsed:           {len(records)} rules")
    print(f"  Main:           {dfs['_counts']['main']}")
    print(f"  Review Later:   {dfs['_counts']['review']}")
    print(f"Skipped:          {skipped}")
    print(f"Needs review:     {needs_review_count}")
    print(f"Unresolved flags: {len(dfs['unresolved'])}")
    print(f"Parse errors:     {len(errors)}")

    if not dfs['unresolved'].empty:
        print("\nUNRESOLVED FLAGS — stop and ask user:")
        for _, row in dfs['unresolved'].iterrows():
            print(f"  - {row['flag']} (field: {row['field']})")

    return dfs['main'], dfs['review'], dfs['stage'], df_errors, dfs['unresolved']



# ── Config Helpers ────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def save_config(config: dict, path: str):
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Config saved: {path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse IBM ODM .m rule files into CSV')
    parser.add_argument('--config', required=True, help='Path to tenant config JSON')
    parser.add_argument('--input',  required=True, help='Root directory of .m files')
    parser.add_argument('--output', required=True, help='Output directory for CSVs')
    parser.add_argument('--prefix', default='ODM',  help='Filename prefix (default: ODM)')
    args = parser.parse_args()

    config = load_config(args.config)
    parse_all(args.input, config, args.output, args.prefix)
