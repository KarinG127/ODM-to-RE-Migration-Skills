---
name: odm-core
description: "Shared library used by odm-defaults and odm-validations. Not a trigger skill — do not invoke directly. Read this file when debugging a shared extraction issue (flags, conditions, dead rules, LOBs) that affects both skills."
---

# ODM Core — Shared Extraction Library

## What this is

`odm_core.py` is the shared foundation for all ODM parser skills. It contains
every function that is identical between defaults and validations parsing:

| Function | Purpose |
|---|---|
| `read_odm_file` | UTF-16/UTF-8 decoding with ODM marker validation |
| `should_skip_file` | Dead rule detection, SectionClaim skip, skip_flag routing |
| `extract_flags` | Claim flags (flow/source), ba_ flags, unknown flag collection |
| `extract_lobs` | LOB include/exclude from content |
| `extract_conditions` | Field conditions from ORIGINAL_BAL block (two-pass) |
| `simplify_conditions` | Cleans up ODM verbose condition syntax |
| `load_config` / `save_config` | Config JSON I/O |
| `write_csv` | UTF-8-sig CSV writer |

## What lives in the skill scripts (NOT here)

| Logic | Lives in |
|---|---|
| `extract_attributes` (InterviewAttributeType.*) | `odm_defaults.py` |
| `_parse_default_value` | `odm_defaults.py` |
| `detect_rule_type` | `odm_defaults.py` |
| `extract_validation` (validationResponse.addError) | `odm_validations.py` |
| `build_row`, `build_stage_row` | each skill script |
| `_build_dataframes`, `_write_outputs` | each skill script |

## When to edit this file

Only when the bug affects BOTH skills equally — meaning it's in:
- Flag parsing logic
- Dead rule detection
- Condition extraction
- LOB extraction
- File decoding

If the bug is only in how defaults are read or how validation errors are parsed,
fix it in the skill-specific script, not here.

## V2 fixes documented here

**Fix 1 — Dead rule detection (V2)**
Previous regex `\band\s+false\s*\)` missed cases without trailing `)`.
V2 strips all legitimate `is false` patterns (field checks + flag checks) from
each BAL line first, then checks for bare `and false`. This means `SomeField is false`
is never mistaken for a dead rule marker.

**Fix 2 — Flow classification (V2)**
Previous approach read only the Claim flag name. V2 reads both the flag name
AND the IS ENABLED direction:
- `Claim:InterviewFlowType_Agent IS ENABLED = false` → Consumer (not Agent)
- `Claim:InterviewFlowType_Consumer IS ENABLED = false` → Agent (not Consumer)

## File location in repo

```
robolt-skills/
  odm-core/
    SKILL.md        ← this file
    odm_core.py     ← shared library
```

## Future skills that will also import odm_core

`odm-instructions` — carrier submission mapping rules (planned, not yet built).
See README.md for the full planned skill structure.
