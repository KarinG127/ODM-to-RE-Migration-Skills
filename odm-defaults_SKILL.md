---
name: odm-defaults
description: "Use this skill when parsing IBM ODM defaults, relevancy, or stage rules from .m files. Triggers: 'parse defaults', 'run odm-defaults', 'parse the ODM', upload a defaults zip. Produces Defaults.csv + supporting CSVs. Stop-and-ask for unknown flags. Pipeline stage 1 of the Progressive migration."
---

# ODM Defaults Parser Skill

## What this skill does

Parses IBM ODM interview rule files (`.m` extension) containing defaults,
relevancy, and stage rules. Produces structured CSVs for review.

This is **Stage 1** of the migration pipeline:

```
ODM .m files  →  [odm-defaults]  →  Defaults.csv  →  [classify]  →  System_Defaults.csv
                                                                   →  Business_Defaults.csv
                                                                   →  [re-codegen]  →  C# classes
```

## Files required

| File | Location | Purpose |
|---|---|---|
| `odm_defaults.py` | `robolt-skills/odm-defaults/` | Parser script |
| `odm_core.py` | `robolt-skills/odm-core/` | Shared extraction library |
| `progressive_config.json` | project root | Flag/LOB classifications |

`odm_core.py` must be in the same directory as `odm_defaults.py` or on `PYTHONPATH`.

## How to run

```bash
python3 defaults/odm_defaults.py \
    --config progressive_config.json \
    --input  /path/to/odm/defaults/ \
    --output /path/to/output/ \
    --prefix PGR_Defaults
```

If the input is a zip file, unzip first:
```bash
unzip HQ2_Interview.zip -d /path/to/odm/defaults/
```

Install dependencies if needed:
```bash
pip install pandas --break-system-packages
```

## Outputs

| File | Contents | Written when |
|---|---|---|
| `{prefix}_Defaults.csv` | All parsed rules (Default + Relevancy + Stage types) | Always |
| `{prefix}_Review_Later.csv` | Rules set aside — see Review Reason column | Non-empty only |
| `{prefix}_Stage_Rules_Review.csv` | Stage rules targeting a specific field | Non-empty only |
| `{prefix}_Active_Flags.csv` | IMPLEMENT flags with reasoning | Non-empty only |
| `{prefix}_Retired_Flags.csv` | SKIP/CLEANUP flags with reasoning | Non-empty only |
| `{prefix}_Unresolved_Flags.csv` | Unknown flags — **stop and ask user** | Non-empty only |
| `{prefix}_Parse_Errors.csv` | Files that failed to parse | Non-empty only |

## Key columns in Defaults.csv

| Column | Description |
|---|---|
| `Page` | Interview stage/page |
| `Field Name` | PolicyData field path |
| `Rule Type` | Default / Relevancy / Stage |
| `UUID` | ODM file UUID — links back to the `.m` file |
| `Flow` | Agent / Consumer / Both |
| `LOBs` | Which lines of business this rule applies to |
| `Source Flag (Raw)` | Raw source flag conditions |
| `Source Scope` | Human-readable source interpretation |
| `Other BA Flags` | Non-source flags with ACTIVE/INACTIVE/SOURCE-DEPENDENT status |
| `Field Conditions` | Verbatim AND/OR expression from ORIGINAL_BAL |
| `Simplified Conditions` | Cleaned version e.g. `LOB = HO3` |
| `Default Value` | Human-readable default (see patterns below) |
| `Needs Review` | YES if unknown flags remain — rows to resolve |
| `Review Reason` | Why rule is in Review Later (empty = main output) |

## Default value patterns

| Output | Meaning |
|---|---|
| `today's year - N` | `DateTime.Now.Year - N` |
| `01/01/(today's year - YearsAtAddress)` | Date from years at address |
| `PurchaseDate as YYYY-MM-DD` | Formatted purchase date |
| `PropertyAddress.ZipCode` | Field reference |
| `PLYearBuilt` | Direct field reference |
| `[Calculated date — see UUID]` | Complex date — check original file |

## Stop-and-ask workflow

If `Unresolved_Flags.csv` is non-empty after a run, **stop before proceeding**.

For each unresolved flag:
1. Look it up in `ld_snapshot.json` if available (see ld-lookup skill)
2. Apply the classification matrix (see below)
3. Ask the user to confirm the classification
4. Update `progressive_config.json`
5. Re-run the parser

Repeat until `Unresolved flags: 0`.

### Unknown flag classification prompts

**Unknown `ba_` flag:**
```
Found new flag: ba_FlagName (appears in N rules, field: FieldName)
LD state: ON/OFF in all envs | mixed
Tenant rules: [PROGRESSIVEPL] / other tenants only / none
Classify as: IMPLEMENT / SKIP / CLEANUP?
Always ON, always OFF, or source-dependent?
```

**Unknown `Claim:` flag:**
```
Found new Claim flag: Claim:FlagName
Category: flow / quote_state / source / covmod / section?
Value (for flow: Agent or Consumer; for others: descriptive string)?
```

### Config update after classification

```python
import json
config = json.load(open('progressive_config.json'))

# ba_ flag
config['business_flags']['ba_NewFlag'] = {
    'classification': 'IMPLEMENT',   # IMPLEMENT / SKIP / CLEANUP
    'always_on': True,               # True / False / None
    'reason': 'Always ON. Only IS ENABLED=true rules fire.'
}

# Claim: flag
config['claim_flags']['Claim:SomeFlag'] = {
    'category': 'quote_state',       # flow / quote_state / source / covmod / section
    'value': 'SomeValue'
}

json.dump(config, open('progressive_config.json', 'w'), indent=2)
# Then re-run the parser
```

## Flag firing logic

| Flag `always_on` | IS ENABLED = true | IS ENABLED = false |
|---|---|---|
| `true` (always ON) | ✅ ACTIVE — fires | ❌ INACTIVE — file skipped |
| `false` (always OFF) | ❌ INACTIVE — file skipped | ✅ ACTIVE — fires |
| `null` (source-dependent) | ❓ SOURCE-DEPENDENT | ❓ SOURCE-DEPENDENT |

## Review Later routing

Driven entirely by config — nothing hardcoded in the script:

```json
"review_later": {
  "prefill_key": "ThirdPartyPrefill",
  "pages": ["AccountInfo", "YourRates"],
  "custom_fields": {
    "VisibleLeak": "review_later",
    "AddressChanged": "main"
  }
}
```

| Key | Effect |
|---|---|
| `prefill_key` | Rules using `getByKey("X")` with no default → Review Later |
| `pages` | All rules for listed pages → Review Later |
| `custom_fields` | `skip` / `main` / `review_later` routing per field |

## What this skill does NOT do

- Does not parse validation rules (`validationResponse.addError`) — use `odm-validations`
- Does not classify defaults as System vs Business — that is the next stage
- Does not generate C# code — that is `re-defaults-codegen` (future, Claude Code)
- Does not parse carrier instruction mappings — use `odm-instructions` (future)

## Next steps after clean CSV

Once `Unresolved_Flags.csv` is empty and the user confirms `Defaults.csv` looks correct:

→ Run the **odm-defaults-classify** skill (planned) to split into:
  - `System_Defaults.csv` — rules that go into the RE as C# classes
  - `Business_Defaults.csv` — rules that go into the SQL database

Classification rules will be provided by the user and documented in that skill.
