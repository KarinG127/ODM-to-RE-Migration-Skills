# ODM-to-RE Migration — Project README

## What this project is

Migrating Progressive's insurance rules from IBM ODM to Bolt's Rule Engine (RE / RoBolt, C#).
Tenant: **Progressive**. RE repo: `C:\Users\%USERNAME%\source\repos\markets`

This README is the permanent source of truth for the migration approach, all files,
and the full pipeline. Future sessions and team members should be able to orient
from this file alone — read this first, then open the relevant SKILL.md.

---

## How to use this README

- **Starting a new session?** → Read the [Session Startup](#session-startup) section
- **Looking for a specific file?** → See [File Inventory](#file-inventory)
- **Confused about a migration stage?** → Each stage has its own section below
- **Something broken?** → Check [Current Blockers](#current-blockers)

---

## Migration overview

The migration is broken into rule types. Each rule type is a self-contained
workstream with its own parse → classify → codegen pipeline:

| Rule Type | Owner | Status |
|---|---|---|
| **Defaults** | You | 🔄 In progress — parse + classify built |
| **Validations** | Coworker | 🔄 In progress — parse built |
| **Relevancy** | TBD | 📋 Planned |
| **Stages** | TBD | 📋 Planned |
| **Direct Reader** | Shared | ✅ Built — field inventory extraction |

---

## 1. Shared Foundation

These files underpin everything. Both parsers import `odm_core.py`.
The config is shared between all parsers.

### Files

| File | Type | Purpose |
|---|---|---|
| `odm_core.py` | Script | Shared extraction library — file reading, flag parsing, LOB extraction, dead rule detection, condition extraction |
| `odm-core_SKILL.md` | Reference | Documents what the core provides and when to edit it. Not a trigger skill |
| `progressive_config.json` | Config | Classified flag registry — `ba_` flags, `Claim:` flags, LOB map, skip flags, review_later routing |

### When to edit `odm_core.py`

Only when the bug affects **both** parsers — flag parsing, dead rule detection,
condition extraction, LOB extraction, or file decoding. If the bug is
defaults-specific or validations-specific, fix it in the skill script instead.

### When to edit `progressive_config.json`

When an unknown flag appears during a parse run. Both team members share this
file — coordinate before updating. See the stop-and-ask workflow in each skill.

### V2 fixes in odm_core

- **Dead rule detection** — strips legitimate `is false` field checks before
  looking for bare `and false` dead markers. Prevents false positives.
- **Flow classification** — reads both the Claim flag name AND the IS ENABLED
  direction. `Claim:InterviewFlowType_Agent IS ENABLED = false` → Consumer.

---

## 2. Defaults

Extract default values from ODM, cross-reference with Direct, classify into
System (→ RE code) and Business (→ SQL database).

**Owner:** You
**Trigger phrase:** `"parse defaults"` / `"classify defaults"`

### Pipeline

```
ODM .m files
    ↓
[odm-defaults]  →  Defaults.csv  (Stage 1 — parse)
    +
Direct_Master.csv
    ↓
[odm-defaults-classify]  →  System_Defaults.csv    (Stage 2 — classify)
                          →  Business_Defaults.csv
                          →  Review_Defaults.csv
                          →  Gaps_Report.csv
                          →  Agent_Consumer_Diff.csv
    ↓
[re-defaults-codegen]  →  C# DefaultRuleCollection classes  (Stage 3 — codegen, Claude Code, PLANNED)
```

### Files

| File | Type | Purpose |
|---|---|---|
| `odm_defaults.py` | Script | Parses ODM `.m` files — extracts `InterviewAttributeType` rules (Default, Relevancy, Stage) |
| `odm-defaults_SKILL.md` | Skill | Trigger skill — full run instructions, flag logic, output column reference, stop-and-ask workflow |
| `odm_defaults_classify.py` | Script | Joins `Defaults.csv` + `Progressive_Direct_Master.csv` — classifies each rule as System or Business |
| `odm-defaults-classify_SKILL.md` | Skill | Trigger skill — classification rules, gap types, radio/control type conflict flags |

### Classification rules

| Condition | Classification |
|---|---|
| Default Value = `""` (empty string) | **System** — cleaning/reset logic |
| Control Type (Direct) = Checkbox | **System** |
| Control Type (Direct) = Stepper | **System** |
| Display Rules contains `hidden` (Direct) | **Business** — hidden field |
| Everything else | **Review** — stop and ask |

### Special flags raised by classifier

| Flag | Meaning |
|---|---|
| `RADIO-CONFLICT` | Direct says Radio/Segmented, ODM has a default — needs decision |
| `CONTROL-TYPE-CONFLICT` | ODM and Direct disagree on control type — Direct wins, verify |
| `ODM-ONLY` | Field in ODM but not in Direct — verify in scope |
| `POSSIBLE-HIDDEN` | Display Rules may indicate hidden but doesn't say "hidden" literally |

### Outputs — Stage 1 (parse)

| File | Contents |
|---|---|
| `{prefix}_Defaults.csv` | All parsed rules (Default + Relevancy + Stage types) |
| `{prefix}_Review_Later.csv` | Rules set aside for separate review |
| `{prefix}_Stage_Rules_Review.csv` | Stage rules targeting a specific field |
| `{prefix}_Active_Flags.csv` | IMPLEMENT flags with reasoning |
| `{prefix}_Retired_Flags.csv` | SKIP/CLEANUP flags |
| `{prefix}_Unresolved_Flags.csv` | Unknown flags — stop and ask |
| `{prefix}_Parse_Errors.csv` | Files that failed to decode |

### Outputs — Stage 2 (classify)

| File | Contents |
|---|---|
| `{prefix}_System_Defaults.csv` | RE implementation targets |
| `{prefix}_Business_Defaults.csv` | SQL database targets |
| `{prefix}_Review_Defaults.csv` | Needs human decision before proceeding |
| `{prefix}_Gaps_Report.csv` | ODM-only and Direct-only gaps |
| `{prefix}_Agent_Consumer_Diff.csv` | Same field, different default per flow |

### Milestones

- ✅ Stage 1 complete when: `Unresolved_Flags.csv` empty, `Defaults.csv` confirmed
- ✅ Stage 2 complete when: `Review_Defaults.csv` empty, both System and Business CSVs confirmed
- 📋 Stage 3: hand off `System_Defaults.csv` to `re-defaults-codegen` (Claude Code)

---

## 3. Validations

Extract validation error rules from ODM, classify, generate RE code.

**Owner:** Coworker
**Trigger phrase:** `"parse validations"`
**Independent of Defaults** — can run in parallel.

### Pipeline

```
ODM validation .m files
    ↓
[odm-validations]  →  Validations.csv  (parse)
    ↓
[re-validations-codegen]  →  C# ValidationRuleCollection classes  (PLANNED, Claude Code)
```

### Files

| File | Type | Purpose |
|---|---|---|
| `odm_validations.py` | Script | Parses ODM `.m` files — extracts `validationResponse.addError` rules |
| `odm-validations_SKILL.md` | Skill | Trigger skill — same stop-and-ask flow as defaults, validation-specific output columns |

### How to identify validation files

Validation `.m` files have:
- Package name containing `Validations` (e.g. `Validations.Progressive_HQ2`)
- `then` block calls `validationResponse.addError(fieldId, "short msg", "full msg")`
- No `InterviewAttributeType` calls

### Outputs

| File | Contents |
|---|---|
| `{prefix}_Validations.csv` | All parsed validation rules |
| `{prefix}_Review_Later.csv` | Rules set aside |
| `{prefix}_Active_Flags.csv` | IMPLEMENT flags |
| `{prefix}_Retired_Flags.csv` | SKIP/CLEANUP flags |
| `{prefix}_Unresolved_Flags.csv` | Unknown flags — stop and ask |
| `{prefix}_Parse_Errors.csv` | Files that failed to decode |

### Milestones

- ✅ Parse complete when: `Unresolved_Flags.csv` empty, `Validations.csv` confirmed
- 📋 Codegen: hand off to `re-validations-codegen` (Claude Code, not yet built)

---

## 4. Relevancy

Extract relevancy rules from ODM — when/whether a field is displayed.

**Owner:** TBD
**Status:** 📋 Planned — not yet started

### What relevancy rules look like in ODM

`then` block sets `InterviewAttributeType.Relevant = true/false` or
`InterviewAttributeType.Mandatory = true/false`. Conditions in the `when`
block control when the field shows or hides.

### Note

Relevancy rules are currently extracted by `odm_defaults.py` as `Rule Type = Relevancy`
rows in `Defaults.csv`. When the relevancy workstream starts, these rows will
be the starting point — no re-parse needed.

### Planned files (not yet built)

| File | Type | Purpose |
|---|---|---|
| `odm_relevancy.py` | Script | Extract and structure relevancy rules from Defaults.csv |
| `odm-relevancy_SKILL.md` | Skill | Trigger skill |
| `re-relevancy-codegen` | Skill | Generate `RelevancyRuleCollection` C# classes (Claude Code) |

---

## 5. Stages

Extract stage/page rules from ODM — which interview page a field belongs to.

**Owner:** TBD
**Status:** 📋 Planned — not yet started

### Note

Stage rules are currently extracted by `odm_defaults.py` as `Rule Type = Stage`
rows and written to `Stage_Rules_Review.csv`. When this workstream starts,
that CSV is the starting point.

In RE, stage assignment may be an attribute decoration rather than a rule class.
This will be confirmed when the workstream begins.

---

## 6. Direct Reader

Extracts the full field inventory from both Progressive Direct Interview Excel
files into a unified master CSV. This is the source of truth for field metadata
used by the classifier and gap analysis.

**Trigger phrase:** `"read directs"`

### Files

| File | Type | Purpose |
|---|---|---|
| `direct_reader.py` | Script | Reads PAA and HQX Excel files, outputs unified master CSV |
| `direct_reader_SKILL.md` | Skill | Trigger skill — sheet handling, column mapping, LOB extraction, warning types |
| `PAA_2_0_Direct_Interview.xlsx` | Data | Agent flow field definitions (source of truth) |
| `HQX2_0_Direct_Interview.xlsx` | Data | Consumer flow field definitions (source of truth) |

### Output

| File | Contents |
|---|---|
| `Progressive_Direct_Master.csv` | All fields from both flows — canonical name, control type, display rules, default value, LOBs, page, flow |
| `Progressive_Direct_Warnings.csv` | Fields with missing LOBs, ambiguous control types, or other issues |

### Sync behavior

On every run, the script first reads the Change Control sheet and compares
the version number against `direct_version_cache.json`. If the version is
unchanged → skip. If changed → full re-read, overwrite master CSV, update cache.
Commit `direct_version_cache.json` to the repo so both team members share
the same version baseline.

### Key columns used downstream

| Column | Used by |
|---|---|
| `Canonical Name` | Join key for classifier |
| `Control Type` | Classification rule (Checkbox/Stepper/Radio) |
| `Display Rules` | Classification rule (hidden → Business) |
| `Default Value` | Gap detection (Direct-only gaps) |
| `LOBs` | Cross-check against ODM LOBs |

---

## 7. Instructions (Carrier Onboarding)

Parse carrier submission mapping rules — not part of the Progressive migration.

**Status:** 📋 Planned stub only — build when starting a carrier onboarding project

### Files

| File | Type | Purpose |
|---|---|---|
| `odm-instructions_SKILL.md` | Stub | Documents planned scope, example file structure (Homesite HO3 RC1), and what to build |

### What instruction files look like

Different from interview rules — `then` block calls:
- `submissionService.createSubmissionMapping(CarrierID, LOB, field, "/xpath/path", DIRECT, "")`
- `relevancyService.createFieldsRelevancy(CarrierID, LOB, [fields], DIRECT, "")`

No `InterviewAttributeType` or `validationResponse` calls.

---

## File inventory

Every file in the project, grouped by area:

### Shared foundation

| File | Status | Do not edit unless... |
|---|---|---|
| `odm_core.py` | ✅ Current | Bug affects both defaults AND validations |
| `odm-core_SKILL.md` | ✅ Current | Core architecture changes |
| `progressive_config.json` | ✅ Current | New unknown flag encountered during a run |

### Defaults workstream

| File | Status | Notes |
|---|---|---|
| `odm_defaults.py` | ✅ Current | Run directly — do not rewrite |
| `odm-defaults_SKILL.md` | ✅ Current | Full parse documentation |
| `odm_defaults_classify.py` | ✅ Current | Run after clean Defaults.csv |
| `odm-defaults-classify_SKILL.md` | ✅ Current | Full classify documentation |

### Validations workstream

| File | Status | Notes |
|---|---|---|
| `odm_validations.py` | ✅ Current | Run directly — do not rewrite |
| `odm-validations_SKILL.md` | ✅ Current | Full parse documentation |

### Direct reader

| File | Status | Notes |
|---|---|---|
| `direct_reader.py` | ✅ Current | Run directly — do not rewrite |
| `direct_reader_SKILL.md` | ✅ Current | Full extraction documentation |
| `PAA_2_0_Direct_Interview.xlsx` | ✅ Current | Do not edit — source of truth |
| `HQX2_0_Direct_Interview.xlsx` | ✅ Current | Do not edit — source of truth |

### Instructions (future)

| File | Status | Notes |
|---|---|---|
| `odm-instructions_SKILL.md` | 📋 Stub | Not yet built — build when needed |

### Obsolete — delete from repo

| File | Reason |
|---|---|
| `odm_parser.py` | Replaced by `odm_defaults.py` + `odm_validations.py` + `odm_core.py` |
| `odm-parser-SKILL.md` | Replaced by the three separate SKILL.md files |
| `odm-parser.skill` | Old format — replaced |

---

## Session startup

| What you want to do | Say this |
|---|---|
| Parse ODM defaults | `"parse defaults"` + upload zip |
| Classify defaults | `"classify defaults"` — confirm `PGR_Defaults.csv` and `Progressive_Direct_Master.csv` are ready |
| Parse ODM validations | `"parse validations"` + upload zip |
| Read Direct files | `"read directs"` |
| Generate C# defaults | `"generate RE code for defaults"` (use Claude Code) |
| Generate C# validations | `"generate RE code for validations"` (use Claude Code) |
| Ask about the project | Just ask — context is in this README |

---

## Team split

| Person | Workstream | Skills | Dependency |
|---|---|---|---|
| You | Defaults | `odm-defaults`, `odm-defaults-classify` | None |
| Coworker | Validations | `odm-validations` | None — fully independent |
| Both | Config | `progressive_config.json` | Coordinate on new unknown flags |

If defaults run first and resolves all unknown flags, coworker starts with 0
unresolved. If he finds a new flag in the validations zip, he classifies it
and updates the shared config.

---

## Current blockers

### ⏳ Pending product approval

| Field | Page | Flow | Question |
|---|---|---|---|
| `RoofUpdated` | Exterior | Agent | Which LOBs apply? |
| `RoofUpdatedYear` | Exterior | Agent | Which LOBs apply? |
| `UnderConstructionCheckList` | Exterior | Agent | Which LOBs apply? |

### 📋 Skills not yet built

| Skill | Blocked on |
|---|---|
| `re-defaults-codegen` | Clean `System_Defaults.csv` + Claude Code setup |
| `re-validations-codegen` | Clean `Validations.csv` + Claude Code setup |
| `gap-analysis` | Clean Defaults.csv + Validations.csv + Direct Master CSV |
| `odm-relevancy` | Defaults workstream complete |
| `odm-instructions` | Carrier onboarding project (not Progressive migration) |

---

## Future options — not in scope now

### Notion-based smart panel

Design was discussed and parked. Build this after the migration is complete.

**What it is:** A Notion database storing the full Direct field inventory,
synced incrementally using row-level hash comparison. Teammates query it
through Claude using the Notion MCP connector — asking questions like
"what fields are shown on the Exterior page for HO3 with a default value?"
and getting answers without opening the Excel.

**Two Notion databases planned:**
- `Progressive Direct — Field Inventory` — one page per field, all metadata as properties, including `Status` (Active / Strikethrough / Deleted), `Row Hash`, `Direct Version`
- `Progressive Direct — Sync Log` — one entry per sync run, tracking fields added/changed/deleted

**Incremental sync logic:** On each run, compute a SHA256 hash of every field row.
Compare against hashes stored in Notion. Only push changes — new fields (INSERT),
modified fields (UPDATE), removed fields (mark Deleted). Unchanged rows cost zero tokens.

**Why Notion over a shared DB:** No infrastructure needed — Notion is already
connected, shareable with the team, and queryable via Claude's MCP connector.

**When to build:** When the migration is complete and the team needs a queryable
source of truth for the next carrier onboarding.

---

## Key conventions

| Convention | Rule |
|---|---|
| Canonical field name | Strip `PL_F###_` prefix from Field ID; fallback to GetQuote Data Dictionary |
| LOB codes | HO3 = Homeowners, HO6 = Condo, HO4 = Renters, MFH = Manufactured Home, DF = Dwelling Fire |
| Flow | Agent = PAA file; Consumer = HQX file; Both = appears in both |
| FlowStage | QQ = Quick Quote, FQ = Full Quote |
| Control type conflicts | Direct wins — flag and ask if unexpected |
| Shared extraction bugs | Fix in `odm_core.py` only — never in skill scripts |
| Scripts | Run as-is — never rewrite, only extend |

---

## Source of truth principle

Each completed stage produces documentation that stands alone. A future engineer
reading the SKILL.md files should understand: what the stage produces, how to
interpret every output column, what decisions were made and why, what feeds in
and what comes out, and all known edge cases.

When this migration is done, the skill files + CSVs + C# classes together form
a complete auditable record of every rule decision made — reusable for the next carrier.
