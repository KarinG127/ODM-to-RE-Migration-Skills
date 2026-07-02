---
name: odm-validations
description: "Use this skill when parsing IBM ODM validation rules from .m files. Triggers: 'parse validations', 'run odm-validations', upload a validations zip. Produces Validations.csv + supporting CSVs. Stop-and-ask for unknown flags. Independent of odm-defaults — can run in parallel."
---

# ODM Validations Parser Skill

## What this skill does

Parses IBM ODM validation rule files (`.m` extension) containing
`validationResponse.addError` calls. Produces structured CSVs for review.

This skill is **independent of odm-defaults** — it can be run by a different
team member in parallel. Both skills share the same `progressive_config.json`.

Pipeline position:
```
ODM validation .m files  →  [odm-validations]  →  Validations.csv  →  [re-validations-codegen]  →  C# classes
```

## How to identify validation files

Validation `.m` files have:
- Package name containing `Validations` (e.g. `Validations.Progressive_HQ2`)
- `then` block calls `validationResponse.addError(fieldId, "short msg", "full msg")`
- No `InterviewAttributeType` calls — those are defaults files

## Files required

| File | Location | Purpose |
|---|---|---|
| `odm_validations.py` | `robolt-skills/odm-validations/` | Parser script |
| `odm_core.py` | `robolt-skills/odm-core/` | Shared extraction library |
| `progressive_config.json` | project root | Flag/LOB classifications |

`odm_core.py` must be in the same directory as `odm_validations.py` or on `PYTHONPATH`.

## How to run

```bash
python3 odm_validations.py \
    --config progressive_config.json \
    --input  /path/to/odm/validations/ \
    --output /path/to/output/ \
    --prefix PGR_Validations
```

If the input is a zip file, unzip first:
```bash
unzip Validations.zip -d /path/to/odm/validations/
```

## Outputs

| File | Contents | Written when |
|---|---|---|
| `{prefix}_Validations.csv` | All parsed validation rules | Always |
| `{prefix}_Review_Later.csv` | Rules set aside — see Review Reason column | Non-empty only |
| `{prefix}_Active_Flags.csv` | IMPLEMENT flags with reasoning | Non-empty only |
| `{prefix}_Retired_Flags.csv` | SKIP/CLEANUP flags with reasoning | Non-empty only |
| `{prefix}_Unresolved_Flags.csv` | Unknown flags — **stop and ask user** | Non-empty only |
| `{prefix}_Parse_Errors.csv` | Files that failed to parse | Non-empty only |

## Key columns in Validations.csv

| Column | Description |
|---|---|
| `Page` | Interview stage/page (from package name) |
| `Field Name` | PolicyData field path |
| `UUID` | ODM file UUID — links back to the `.m` file |
| `Flow` | Agent / Consumer / Both |
| `LOBs` | Which lines of business this rule applies to |
| `Source Flag (Raw)` | Raw source flag conditions |
| `Source Scope` | Human-readable source interpretation |
| `Other BA Flags` | Non-source flags with ACTIVE/INACTIVE/SOURCE-DEPENDENT status |
| `Field Conditions` | Verbatim AND/OR expression from ORIGINAL_BAL |
| `Simplified Conditions` | Cleaned version e.g. `LOB = HO3` |
| `Error Message (Short)` | Short validation error message |
| `Error Message (Full)` | Full validation error message |
| `Needs Review` | YES if unknown flags remain |
| `Review Reason` | Why rule is in Review Later (empty = main output) |

## Stop-and-ask workflow

Same as odm-defaults — if `Unresolved_Flags.csv` is non-empty, stop.

For each unresolved flag:
1. Look it up in `ld_snapshot.json` if available
2. Apply the classification matrix
3. Ask the user to confirm
4. Update `progressive_config.json`
5. Re-run

### Config update after classification

```python
import json
config = json.load(open('progressive_config.json'))

config['business_flags']['ba_NewFlag'] = {
    'classification': 'IMPLEMENT',
    'always_on': True,
    'reason': 'Always ON. Only IS ENABLED=true rules fire.'
}

json.dump(config, open('progressive_config.json', 'w'), indent=2)
```

## Flag firing logic

Same as odm-defaults — see odm-defaults SKILL.md for the full table.
Both skills share the same flag classification logic from `odm_core.py`.

## Shared config

`progressive_config.json` is shared between odm-defaults and odm-validations.
If the defaults run already resolved all unknown flags, the validations run
will start with 0 unresolved flags — no additional classification needed
unless the validations zip introduces new flags not seen in defaults.

## What this skill does NOT do

- Does not parse defaults/relevancy/stage rules — use `odm-defaults`
- Does not generate C# code — that is `re-validations-codegen` (future, Claude Code)
- Does not parse carrier instruction mappings — use `odm-instructions` (future)

## Next steps after clean CSV

Once `Unresolved_Flags.csv` is empty and the user confirms `Validations.csv`
looks correct → hand off to **re-validations-codegen** (future Claude Code skill)
to generate `ValidationRuleCollection` C# classes directly into the repo.
