#!/usr/bin/env python3
"""
ODM Validations Parser
=======================
Parses IBM ODM validation rule files (.m extension) and extracts:
  - Validation rules         → {prefix}_Validations.csv
  - Rules to review later    → {prefix}_Review_Later.csv
  - Active feature flags     → {prefix}_Active_Flags.csv
  - Retired feature flags    → {prefix}_Retired_Flags.csv
  - Unresolved flags         → {prefix}_Unresolved_Flags.csv  (stop and ask user)
  - Parse errors             → {prefix}_Parse_Errors.csv

Depends on: odm_core.py (must be in same directory or on PYTHONPATH)
Config:     tenant config JSON (e.g. progressive_config.json)

Usage:
    python3 odm_validations.py \
        --config progressive_config.json \
        --input  /path/to/odm/validations/folder/ \
        --output /path/to/output/ \
        --prefix PGR_Validations

Stop-and-ask workflow:
    If Unresolved_Flags.csv is non-empty, stop.
    Look up each flag in ld_snapshot.json (if available).
    Ask the user for classification.
    Update the config JSON.
    Re-run. Repeat until Unresolved_Flags.csv is empty.

How to identify validation files:
    Package name contains 'Validations' (e.g. Validations.Progressive_HQ2)
    then block calls: validationResponse.addError(fieldId, shortMsg, fullMsg)
    No InterviewAttributeType calls — those are defaults files.

Pipeline position:
    INPUT:  ODM .m files (validation rules — separate folder/zip from defaults)
    OUTPUT: Validations.csv — reviewed and confirmed clean CSV
    NEXT:   re-validations-codegen (future Claude Code skill)

Independent of odm-defaults — can be run in parallel by a different team member.
Both skills share the same progressive_config.json — no changes needed if config
was already built during the defaults run.
"""

import re, os, argparse
import pandas as pd
from typing import Optional

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'core'))
from odm_core import (
    read_odm_file, should_skip_file, extract_flags, extract_lobs,
    extract_conditions, simplify_conditions, load_config, save_config, write_csv
)


# ── Validation Extraction (validations-specific) ──────────────────────────────

def extract_validation(content: str) -> dict:
    """
    Extract validation error details from the then block.
    Validation files call: validationResponse.addError(fieldId, shortMsg, fullMsg)

    Returns dict with:
      field_name   — PolicyData field path (from fieldId assignment)
      error_short  — short error message (first string arg after fieldId)
      error_full   — full error message (second string arg after fieldId)

    Note: fieldId is set as a variable before addError is called:
      fieldId = "PolicyData/SomeField";
      validationResponse.addError(fieldId, "Short msg", "Full msg");
    """
    attrs = {}

    # Field ID from variable assignment in then block
    fm = re.search(r'fieldId\s*=\s*"PolicyData/([^"]+)"', content)
    if fm:
        attrs['field_name'] = fm.group(1)

    # Error messages from addError call
    # Pattern: addError(fieldId, "short message", "full message")
    em = re.search(
        r'validationResponse\.addError\s*\(\s*fieldId\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"',
        content)
    if em:
        attrs['error_short'] = em.group(1).strip()
        attrs['error_full']  = em.group(2).strip()

    return attrs


# ── Review Later Routing ──────────────────────────────────────────────────────

def get_review_reason(r: dict, content: str, config: dict) -> str:
    """
    Route rules to Review Later based on config.
    Same logic as defaults — pages and custom fields routing apply here too.
    """
    rl = config.get('review_later', {})

    for page in rl.get('pages', []):
        if r.get('page') == page:
            return f'{page} — rules for this page, review separately'

    if r.get('field_name') and r['field_name'].startswith('CustomFields/'):
        field_short = r['field_name'].split('/')[-1]
        routing = rl.get('custom_fields', {}).get(field_short)
        if routing == 'review_later':
            return f'CustomFields — validation only, needs separate review ({field_short})'

    return ''


# ── Main Single-File Parser ───────────────────────────────────────────────────

def parse_odm_file(filepath: str, config: dict, source_flags: set) -> Optional[dict]:
    content = read_odm_file(filepath)

    if should_skip_file(content, config):
        return None

    # Skip files that are not validation rules
    if 'validationResponse.addError' not in content:
        return None

    r = {}
    r['uuid'] = os.path.basename(filepath).replace('.m', '')

    pkg = re.search(r'ilog\.rules\.package_name\s*=\s*"([^"]+)"', content)
    r['page'] = pkg.group(1).split('.')[-1] if pkg else None

    bm = re.search(r'ilog\.rules\.business_name\s*=\s*"([^"]+)"', content)
    r['business_name'] = bm.group(1) if bm else None

    r['flow'], r['sources'], r['ba_flags_raw'], r['unknown_flags'] = extract_flags(content, config)
    r['lob_includes'], r['lob_excludes'] = extract_lobs(content, config)

    validation = extract_validation(content)
    r.update(validation)

    r['conditions'] = extract_conditions(content)
    r['simplified_conditions'] = simplify_conditions(r['conditions'])

    # Skip files where a non-source flag is confirmed inactive
    for f in r['ba_flags_raw']:
        if f['base'] not in source_flags and f.get('fires') is False:
            return None

    r['review_reason'] = get_review_reason(r, content, config)

    if r.get('field_name') and r['field_name'].startswith('CustomFields/'):
        field_short = r['field_name'].split('/')[-1]
        known_custom = config.get('review_later', {}).get('custom_fields', {})
        if field_short not in known_custom:
            r['unknown_flags'] = r.get('unknown_flags', []) + [
                f"CustomFields/{field_short} — unknown custom field, needs classification"]

    unresolved = [f for f in r['ba_flags_raw'] if f['classification'] == 'UNRESOLVED']
    r['needs_review'] = bool(r['unknown_flags'] or unresolved)
    return r


# ── Row Builder ───────────────────────────────────────────────────────────────

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
            fires  = f.get('fires')
            status = ('ACTIVE' if fires is True else
                      ('INACTIVE' if fires is False else 'SOURCE-DEPENDENT'))
            other_flag_parts.append(f"{raw_str} -> {f['classification']} {status}")

    return {
        'Page':                  r.get('page', ''),
        'Field Name':            r.get('field_name', ''),
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
        'Error Message (Short)': r.get('error_short', ''),
        'Error Message (Full)':  r.get('error_full', ''),
        'Needs Review':          'YES' if r.get('needs_review') else 'NO',
        'Unknown Flags':         ', '.join(r.get('unknown_flags', [])),
        'Review Reason':         r.get('review_reason', ''),
    }


# ── Output Building ───────────────────────────────────────────────────────────

def _build_dataframes(records: list, source_flags: set, config: dict) -> dict:
    main_records   = [r for r in records if not r.get('review_reason')]
    review_records = [r for r in records if r.get('review_reason')]

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
        'unresolved': pd.DataFrame(unresolved).drop_duplicates(subset=['flag']) if unresolved else pd.DataFrame(),
        'active':     pd.DataFrame(active)  if active  else pd.DataFrame(),
        'retired':    pd.DataFrame(retired) if retired else pd.DataFrame(),
        '_counts':    {'main': len(main_records), 'review': len(review_records)},
    }


def _write_outputs(dfs: dict, output_dir: str, prefix: str):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nWriting CSVs to: {output_dir}")

    def write_if_nonempty(df, name):
        if not df.empty:
            write_csv(df, os.path.join(output_dir, f"{prefix}_{name}.csv"))

    write_csv(dfs['main'],               os.path.join(output_dir, f"{prefix}_Validations.csv"))
    write_if_nonempty(dfs['review'],     'Review_Later')
    write_if_nonempty(dfs['active'],     'Active_Flags')
    write_if_nonempty(dfs['retired'],    'Retired_Flags')
    write_if_nonempty(dfs['unresolved'], 'Unresolved_Flags')


# ── Batch Processing ──────────────────────────────────────────────────────────

def parse_all(root_dir: str, config: dict, output_dir: str, prefix: str = 'PGR'):
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

    dfs       = _build_dataframes(records, source_flags, config)
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

    return dfs['main'], dfs['review'], df_errors, dfs['unresolved']


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse ODM validation rules into CSV')
    parser.add_argument('--config', required=True, help='Path to tenant config JSON')
    parser.add_argument('--input',  required=True, help='Root directory of .m files')
    parser.add_argument('--output', required=True, help='Output directory for CSVs')
    parser.add_argument('--prefix', default='PGR',  help='Filename prefix (default: PGR)')
    args = parser.parse_args()

    config = load_config(args.config)
    parse_all(args.input, config, args.output, args.prefix)
