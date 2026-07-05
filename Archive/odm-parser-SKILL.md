---
name: odm-parser
description: "Use this skill whenever you need to parse IBM ODM rule files (.m extension) for any ODM-to-RE migration project. Handles single file inspection or batch processing of thousands of files. Two-layer architecture: generic parser script + per-tenant JSON config. Produces Rules, Review Later, Active Flags, Retired Flags CSVs. Works for any tenant — start with an empty config and build it up iteratively. When an unknown flag or field is encountered, stop and ask the user."
license: Internal — Bolt Engineering
---

# ODM `.m` File Parser Skill

## How To Run

```bash
python3 odm_parser.py \
  --config tenant_config.json \
  --input /path/to/odm/folder/ \
  --output /path/to/output/ \
  --prefix ODM_Full
```

Copy `odm_parser.py` from the Project files. If the user uploads a zip, unzip first.
For a new tenant, start with an empty config (see New Tenant section below).

---

## Two-Layer Architecture

| Layer | File | Contains |
|---|---|---|
| Generic engine | `odm_parser.py` | Parser logic — never changes between tenants |
| Tenant knowledge | `{tenant}_config.json` | All tenant-specific flags, LOBs, routing — grows over sessions |

**Zero tenant logic is hardcoded in the script.** Everything is driven by the config.

For how the script is structured internally (extraction / output building / I/O), see the Internal Architecture section below.

---

## Flag Firing Logic

```
IS ENABLED IN features is true  → rule fires when the flag is ON
IS ENABLED IN features is false → rule fires when the flag is OFF
```

| Flag `always_on` | IS ENABLED = true | IS ENABLED = false |
|---|---|---|
| `true` (always ON) | ✅ ACTIVE — fires | ❌ INACTIVE — never fires |
| `false` (always OFF) | ❌ INACTIVE — never fires | ✅ ACTIVE — fires |
| `null` (source-dependent) | ❓ SOURCE-DEPENDENT | ❓ SOURCE-DEPENDENT |

**Source identity flags** are listed in `config['source_flags']['identity_flags']` — never hardcoded in the script. For a new tenant, populate this list with whatever ba_ flags identify the source system (equivalent of odysseyapi/LightApi/getquoteapi for Progressive). Leave the list empty if no source flags exist yet.

---

## LaunchDarkly Flag Classification Matrix

When classifying an unknown flag, cross-reference with the LD snapshot (`ld_snapshot.json`). Use this matrix to determine `always_on` and whether to include the flag in conditions:

| LD State | Tenant Rules | Classification | `always_on` | Notes |
|---|---|---|---|---|
| ON in all envs | None (global) | `IMPLEMENT` | `null` | Include in conditions. Config `reason`: `"Always ON in all envs — conditions included, consider hardcoding true after team verification"` |
| OFF in all envs | None (global) | `IMPLEMENT` | `false` | Treat as always false — only IS ENABLED=false rules fire |
| ON in all envs | Progressive rule exists | `IMPLEMENT` | `null` | Include in conditions. Config `reason`: `"Always ON in all envs for Progressive — conditions included, consider hardcoding true after team verification"` |
| ON in all envs | Other tenant rules only (e.g. USAA) | Depends on fallthrough | `true` or `false` | Progressive gets the fallthrough value — check fallthrough variation to determine `always_on` |
| Mixed across envs | Any | `IMPLEMENT` | `null` | Include in conditions as-is |
| Not found in LD | — | `SKIP` | `false` | Dead/removed flag — never fires |
| Tags = other tenant only (AAH, KRAFTLAKEX, VWCANADA, etc.) | — | `SKIP` | `false` | Other tenant flag — exclude entirely |

### Fallthrough logic (for flags with other-tenant rules)
When a flag is ON but has rules only for other tenants, Progressive gets the **fallthrough** behavior:
- Fallthrough variation = `true` → Progressive always gets ON → `always_on: true`
- Fallthrough variation = `false` → Progressive always gets OFF → `always_on: false`
- Fallthrough variation = `null/unknown` → treat as `always_on: null`, include in conditions

---

## Stop and Ask — Unknown Flags & Fields

When the parser finds something unclassified, **always stop and ask the user**. If an `ld_snapshot.json` is available in the project, look up the flag there first and apply the LaunchDarkly Classification Matrix above before asking — this often resolves the classification without needing user input.

### Unknown `ba_` flag:
```
I found a new flag: ba_SomeFlagName (appears in N rules)
LD state: ON in all envs / OFF in all envs / mixed
Tenant rules: [PROGRESSIVEPL] / [USAA] / none
- Classify as: IMPLEMENT / SKIP / CLEANUP?
- Is it always ON, always OFF, or source-dependent?
```
Then add to config `business_flags` and re-run.

### Unknown `Claim:` flag:
Ask which category: `flow` / `quote_state` / `source` / `covmod` / `section` (section = ignored).
Then add to config `claim_flags` and re-run.

### Unknown non-`ba_`/non-`Claim:` flag (e.g. ViewMode, DataDictionary):
```
I found an unrecognised flag: FlagName
- Should rules containing it be excluded entirely?
- If not, is it always ON or always OFF?
```
Then add to config `skip_flags` and re-run.

### Unknown `CustomFields/` field:
```
I found a new CustomField: CustomFields/FieldName
- skip   — retired field, exclude entirely
- main   — active field with default value rules, include in main output
- review_later — relevancy only, no default, set aside for later
```
Then add to config `review_later.custom_fields` and re-run.

### After any classification — update config and re-run:
```python
import json
config = json.load(open('tenant_config.json'))

# ba_ flag
config['business_flags']['ba_NewFlag'] = {
    'classification': 'IMPLEMENT',  # IMPLEMENT / SKIP / CLEANUP
    'always_on': True,              # True / False / None
    'reason': 'Always ON. Only IS ENABLED=true rules fire.'
}

# Claim: flag
config['claim_flags']['Claim:SomeFlag'] = {
    'category': 'quote_state',  # flow / quote_state / source / covmod / section
    'value': 'SomeValue'
}

# Whole-file skip flag
config['skip_flags']['SomeFlag'] = {
    'classification': 'SKIP',
    'always_on': False,
    'reason': 'Reason for excluding.'
}

# CustomField routing
config['review_later']['custom_fields']['FieldName'] = 'skip'  # or 'main' / 'review_later'

json.dump(config, open('tenant_config.json', 'w'), indent=2)
# Then re-run the parser
```

---

## Review Later Routing

All routing is driven by `review_later` in the config — **nothing is hardcoded in the script**.
Rules routed here appear in `{prefix}_Review_Later.csv` with a `Review Reason` column.

```json
"review_later": {
  "prefill_key": "ThirdPartyPrefill",
  "pages": ["AccountInfo", "YourRates"],
  "custom_fields": {
    "QBEOnlineBuy":               "skip",
    "AddressChanged":             "main",
    "VisibleLeak":                "review_later",
    "HasWaterHeaterBeenReplaced": "review_later"
  }
}
```

| Key | What it does |
|---|---|
| `prefill_key` | Rules containing `getByKey("X")` with no default → Review Later |
| `pages` | All rules for these pages → Review Later |
| `custom_fields` | Per-field routing: `skip` / `main` / `review_later` |

For a new tenant — start with empty `pages: []`, `custom_fields: {}`, no `prefill_key`.
Add entries as you discover which pages/fields need to be set aside.

---

## CSV Output

| File | Contents | Written when |
|---|---|---|
| `{prefix}_Rules.csv` | All clean, actionable rules | Always |
| `{prefix}_Review_Later.csv` | Rules set aside — see `Review Reason` column | Non-empty only |
| `{prefix}_Stage_Rules_Review.csv` | Stage rules targeting a specific field | Non-empty only |
| `{prefix}_Active_Flags.csv` | IMPLEMENT flags with reasoning | Non-empty only |
| `{prefix}_Retired_Flags.csv` | SKIP/CLEANUP flags with reasoning | Non-empty only |
| `{prefix}_Unresolved_Flags.csv` | Unknown flags needing classification | Non-empty only |
| `{prefix}_Parse_Errors.csv` | Files that failed to parse | Non-empty only |

### Key Columns in Rules CSV

| Column | Description |
|---|---|
| `Page` | Interview stage/page |
| `Field Name` | PolicyData field name |
| `Rule Type` | Default / Relevancy / Stage |
| `UUID` | ODM file UUID — use to look up the original `.m` file |
| `Flow` | Agent / Consumer / Both |
| `Source Flag (Raw)` | Raw source flag conditions (`&` = AND) |
| `Source Scope` | Human-readable interpretation |
| `Other BA Flags` | Non-source flags with `-> CLASSIFICATION ACTIVE/INACTIVE/SOURCE-DEPENDENT` |
| `Field Conditions` | Verbatim AND/OR expression from ORIGINAL_BAL |
| `Simplified Conditions` | Cleaner version e.g. `LOB = HO3` instead of `Lobses contain PersonalHome` |
| `Default Value` | Simplified default (see patterns below) |
| `Review Reason` | Why this rule is in Review Later (empty = main output) |

### Calculated Default Value Patterns

| Value shown | RE C# equivalent |
|---|---|
| `today's year - N` | `DateTime.Now.Year - N` |
| `01/01/(today's year - YearsAtAddress)` | `new DateTime(DateTime.Now.Year - a.YearsAtAddress, 1, 1)` |
| `PLYearBuilt` | `a.PLYearBuilt` |
| `PurchaseDate as YYYY-MM-DD` | `a.PurchaseDate.ToString("yyyy-MM-dd")` |
| `PurchaseDate month/15/year` | `new DateTime(a.PurchaseDate.Year, a.PurchaseDate.Month, 15)` |
| `PropertyAddress.ZipCode` | `a.PropertyAddress.ZipCode` |
| `EffectiveDate` | `a.EffectiveDate` |

---

## New Tenant Workflow

**Step 1 — Create an empty config:**
```json
{
  "tenant": "TenantName",
  "lob_map": {},
  "claim_flags": {},
  "skip_flags": {},
  "source_flags": {
    "identity_flags": [],
    "matrix": {},
    "interpretation": {}
  },
  "business_flags": {},
  "review_later": {
    "prefill_key": "",
    "pages": [],
    "custom_fields": {}
  }
}
```

**Step 2 — Run the parser:**
```bash
python3 odm_parser.py --config tenant_config.json --input /path/to/odm/ --output /output/ --prefix ODM
```

**Step 3 — Classify unknowns:**
The parser will report unresolved flags. Stop, ask the user about each one, update the config, re-run. Repeat until `Unresolved flags: 0`.

**Step 4 — Configure Review Later:**
Ask the user: "Which pages should be set aside for later review?" and "Is there a prefill vendor key?" Add their answers to `review_later` in the config.

**Step 5 — Download clean CSVs.**
The config is now the tenant's knowledge base. Save it for future sessions.

---

## Config Structure Quick Reference

```json
{
  "tenant": "TenantName",
  "lob_map":        { "ManufacturedHome": "MFH", "PersonalHome": "HO3", ... },
  "claim_flags":    { "Claim:X": { "category": "flow|quote_state|source|covmod|section", "value": "..." } },
  "skip_flags":     { "ViewMode": { "classification": "SKIP", "always_on": false, "reason": "..." } },
  "source_flags":   {
    "identity_flags": ["ba_odysseyapi", "ba_LightApi", "ba_getquoteapi"],
    "matrix": {...},
    "interpretation": {...}
  },
  "business_flags": { "ba_X": { "classification": "IMPLEMENT|SKIP|CLEANUP", "always_on": true|false|null, "reason": "..." } },
  "review_later":   { "prefill_key": "...", "pages": [...], "custom_fields": { "FieldName": "skip|main|review_later" } }
}
```

---

## Internal Architecture

The script has three logical layers inside a single file:

| Layer | Functions | Responsibility |
|---|---|---|
| **Extraction** | `read_odm_file`, `should_skip_file`, `extract_flags`, `extract_lobs`, `extract_attributes`, `extract_conditions` | Parse one `.m` file into a raw record dict |
| **Output building** | `build_row`, `build_stage_row`, `_build_dataframes` | Turn records into typed DataFrames |
| **I/O** | `_write_outputs`, `write_csv`, `parse_all` | Walk directories, orchestrate, write CSVs |

`parse_all` is a thin orchestrator — it walks files, calls `parse_odm_file`, then delegates to `_build_dataframes` and `_write_outputs`. Keep it that way.

### Condition extraction — two-pass approach

`extract_conditions` uses a deliberate two-pass design:

**Pass 1** strips the ODM preamble from the raw ORIGINAL_BAL block line by line, stopping at `then`. Preamble patterns skipped (in order): `isInFeature(`, `IS ENABLED IN features is`, `definitions`, `set 'currentStage'`, `if` (standalone), `all/one of the following`, `currentStage is`. Once a line doesn't match any preamble pattern, `in_conditions` flips to `True` and stays there — all remaining lines before `then` are kept as raw condition candidates.

**Pass 2** drops standalone boilerplate from the candidate list: bare `true`, `and/or true`, `SET VAR` lines. The remainder is joined and cleaned.

If no condition lines survive both passes, returns `'true'` (rule fires unconditionally given its flags).

### Default value parsing — `_parse_default_value`

Separated from `extract_attributes` into its own function. Uses a flat if/elif chain ordered from most-specific to most-general. Each branch owns its own `re.search` call — never reuse a match object across the test and the output. Adding a new date pattern = one new `if` block at the right priority position.

---

## Edge Cases & Conventions

- **Rule type priority**: `default_value` → `stage_set` (no field) → `relevant` → `mandatory`/`control_type` → `Stage` fallback. A rule with both `stage_set` and `mandatory` is a Stage rule, not Relevancy.
- **Encoding**: Reader validates content by checking for `package` or `ORIGINAL_BAL` — prevents false decoding from BOM-like bytes in UTF-8 files.
- **SectionClaim rules**: Always excluded — they control UI section visibility, not field attributes.
- **Dead rules (`and false`)**: ORIGINAL_BAL containing `and false)` → excluded entirely.
- **SET VAR lines**: Field identification, not conditions — excluded from Field Conditions column.
- **`and true` / `or true`**: ODM boilerplate — excluded from Field Conditions.
- **Empty conditions**: Output as `true` — rule fires unconditionally given its feature flags.
- **Flag name whitespace**: Trailing spaces in flag names stripped automatically.
- **`&` in flag columns**: Means AND — all flags apply simultaneously to the same rule.
- **Stage rules**: Only included if they target a specific field (have `fieldId`).
- **`PropertyAddress` defaults**: Can be two levels deep (`PropertyAddress.State`) — the pattern handles both `PropertyAddress.Field` and nested paths via regex, not string split.
