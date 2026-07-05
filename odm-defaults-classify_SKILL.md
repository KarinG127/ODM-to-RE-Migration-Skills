---
name: odm-defaults-classify
description: "Use this skill after odm-defaults has produced a clean Defaults.csv with 0 unresolved flags. Triggers: 'classify defaults', 'run odm-defaults-classify', 'split system and business defaults'. Takes ODM Defaults.csv + Direct Master CSV and classifies each default rule as System (→ RE C# code) or Business (→ SQL database). Raises flags for radio conflicts, agent/consumer divergence, control type conflicts, and gaps. Pipeline stage 2 of the Progressive migration."
---

# ODM Defaults Classifier Skill

## What this skill does

Joins ODM default rules with Direct field metadata to classify each rule as:

- **System** → goes into RE as C# `DefaultRuleCollection` classes
- **Business** → goes into SQL database
- **Review** → cannot auto-classify, needs human decision before proceeding

This is **Stage 2** of the defaults pipeline:

```
Defaults.csv  +  Progressive_Direct_Master.csv
        ↓
[odm-defaults-classify]
        ↓
System_Defaults.csv    →  [re-defaults-codegen]  →  C# classes
Business_Defaults.csv  →  SQL import
Review_Defaults.csv    →  human decisions needed
Gaps_Report.csv        →  missing rules or out-of-scope fields
Agent_Consumer_Diff.csv → same field, different defaults by flow
```

## Prerequisites

Both inputs must be ready and confirmed clean before running:
- `{prefix}_Defaults.csv` from `odm-defaults` — 0 unresolved flags
- `Progressive_Direct_Master.csv` from `direct-reader`

## How to run

```bash
python3 odm_defaults_classify.py \
    --odm    /path/to/PGR_Defaults.csv \
    --direct /path/to/Progressive_Direct_Master.csv \
    --output /path/to/output/ \
    --prefix PGR
```

## Classification rules

| Rule | Classification | Logic |
|---|---|---|
| Default Value = `""` (empty string) | **System** | Cleaning/reset logic for parent-child questions |
| Control Type (Direct) = Checkbox | **System** | Checkbox field |
| Control Type (Direct) = Stepper | **System** | 0/1 numeric stepper |
| Display Rules contains `hidden` | **Business** | Hidden field — user never sees it |
| Everything else | **Review** | Cannot auto-classify — stop and ask |

### Why this split

**System defaults** go into RE because they describe UI behaviour — what value
a field resets to, how a stepper initialises, what a checkbox clears to. These
are structural and must be in the code.

**Business defaults** go into SQL because they represent configurable business
decisions — what value a hidden field is pre-set to. These may change per
carrier, state, or product without requiring a code deploy.

**Cleaning logic** (empty string default) is always System — it resets child
questions when a parent changes (e.g. pool → pool features). This is always
a structural rule.

## Outputs

| File | Contents | Written when |
|---|---|---|
| `{prefix}_System_Defaults.csv` | Rules classified as System | Always |
| `{prefix}_Business_Defaults.csv` | Rules classified as Business | Always |
| `{prefix}_Review_Defaults.csv` | Rules needing human decision | Non-empty only |
| `{prefix}_Gaps_Report.csv` | ODM-only and Direct-only gaps | Non-empty only |
| `{prefix}_Agent_Consumer_Diff.csv` | Fields with different defaults per flow | Non-empty only |

## Key columns in output CSVs

All output files carry the original ODM columns plus these enriched columns:

| Column | Description |
|---|---|
| `Canonical` | Stripped field name used for join (`PolicyData/X` → `X`) |
| `Direct Control Type` | Control type from Direct (authoritative) |
| `Direct Display Rules` | Raw display rules from Direct |
| `Direct Default Value` | Default value as specified in Direct (may differ from ODM) |
| `Direct LOBs` | LOBs from Direct (cross-check against ODM LOBs) |
| `Classification` | System / Business / Review |
| `Classification Reason` | Why this classification was assigned |
| `Flags` | Pipe-separated special flags (see below) |

## Special flags — stop and ask on these

The script surfaces these flags in `Review_Defaults.csv` and prints them to
console. Each must be resolved before moving to codegen.

### RADIO-CONFLICT
ODM has a default value for a field that Direct classifies as Radio (or
Segmented Control). Radio questions are not checkboxes — ODM may have
incorrectly encoded this. Direct is the source of truth for control type.

**Action:** Look at the field in the Direct. Decide whether the default should
exist. If yes, decide the classification manually. If no, remove the ODM rule.

### CONTROL-TYPE-CONFLICT
ODM's `FieldControl` attribute and Direct's `Control Type` column disagree.
Direct wins per convention, but this should be verified.

**Action:** Check the actual UI. Update ODM classification in the config if needed.

### ODM-ONLY
Field has an ODM default rule but does not appear in the Direct at all.

**Action:** Verify the field is in scope for the migration. If it's a system
field not shown in the interview (e.g. internal tracking), classify manually.
If it shouldn't exist, flag for cleanup.

### POSSIBLE-HIDDEN
Display Rules contain a phrase that may indicate the field is hidden
(`not visible`, `not displayed`, etc.) but not the literal word `hidden`.

**Action:** Confirm whether this should be treated as hidden → Business.

## Gap types in Gaps_Report.csv

| Gap Type | Meaning | Action |
|---|---|---|
| `ODM-ONLY` | ODM rule exists, field not in Direct | Verify field is in scope |
| `DIRECT-ONLY` | Direct specifies a default, no ODM rule exists | Rule must be written in RE from scratch |

Direct-only gaps are the most important — these are defaults defined in the
product spec that never made it into ODM, meaning they are currently missing
from the system entirely.

## Agent/Consumer divergence

`Agent_Consumer_Diff.csv` lists fields where the same canonical field has
different default values for Agent flow vs Consumer flow.

This is not necessarily wrong — some defaults are intentionally different
between PAA 2.0 and HQX 2.0. But each difference must be confirmed as
intentional before writing the RE rules.

**Pattern to watch for:** if Agent default = `false` and Consumer default = `true`
(or vice versa), this means two separate RE rules will be needed, one per flow.

## Join logic

ODM `Field Name` → strip `PolicyData/` prefix → match to Direct `Canonical Name`.

If the join fails (ODM-ONLY), the script checks whether the suffix after `PolicyData/`
contains a sub-path (e.g. `FQData/SomeName`) — these are flagged separately as
they may be out-of-scope fields. If you see an unexpected join failure, check
whether the Direct uses a different name for the field and report it.

## What this skill does NOT do

- Does not generate C# code — that is `re-defaults-codegen` (future, Claude Code)
- Does not import to SQL — that is a separate database operation
- Does not modify the Direct or ODM files
- Does not re-run the ODM parser — always start from a confirmed clean `Defaults.csv`

## Next steps after clean classification

Once `Review_Defaults.csv` is empty (all items resolved) and both System and
Business CSVs are confirmed:

→ **System_Defaults.csv** → hand off to `re-defaults-codegen` (Claude Code)
  to generate `DefaultRuleCollection` C# classes directly into the repo.

→ **Business_Defaults.csv** → hand off to database team for SQL import.
