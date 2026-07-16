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
python3 defaults/odm_defaults_classify.py \
    --odm    /path/to/PGR_Defaults.csv \
    --direct /path/to/Progressive_Direct_Master.csv \
    --output /path/to/output/ \
    --prefix PGR
```

## Classification rules

| Rule | Classification | Logic |
|---|---|---|
| Empty default + `Visible=false` | **System** | Cleaning/reset logic — dependency field changed |
| Display Rules contains hidden keyword | **Business** | Field is hidden — user never sees it |
| Default text says "if hidden" / "when hidden" | **Business** | Conditionally hidden — default applies when field is not shown |
| Control Type (Direct) = Checkbox | **System** | Checkbox field |
| Control Type (Direct) = Stepper | **System** | 0/1 numeric stepper |
| Empty default + `Visible=true` (or not set) | **Review** | Not standard cleaning — stop and ask |
| Everything else | **Review** | Cannot auto-classify — stop and ask |

### Cleaning logic — the confirmed signal

A cleaning rule wipes a child field's value when its parent/dependency changes.
The reliable signal is **empty DefaultValue + `Visible=false`** in the ODM `then`
block — confirmed across the dataset (101 rules match, independent of folder name).

Do NOT rely on the `_Cleaned-dt` folder name — cleaning rules appear in regular
folders too (`TheBasics-dt`, `Triage-dt`).

**Dead rules win over cleaning:** a rule with `and false` in its conditions is
dead garbage and is skipped at the parse stage — even if it has the cleaning
signature. It never reaches the classifier. (See core SKILL.md — dead rule detection.)

**Empty default + Visible=true** is NOT cleaning — it's flagged
`EMPTY-DEFAULT-NOT-HIDDEN` for review (e.g. the `CoSSN` fields).

### What counts as hidden

Three patterns detected:

**Pattern A — Literal hidden keyword** in Display Rules:
`hidden`, `not for display`, `not displayed`, `not visible`, `never shown`, `not shown`

**Pattern B — Conditional hidden signal** in the default value text:
`if hidden`, `when hidden`, `if not displayed`, `if not shown`
e.g. `DwellingOccupancy` default = "If hidden then Owner-Primary" → Business

**Pattern C — Conditional hiding (flagged for confirmation)**
Display Rules have conditions (AND/OR/IF/state) AND default value also references
conditions (state/if/when/LOB). The field may be hidden for exactly the cases
where the default applies — like `DogsBreedsSelection` (shown when state NOT in list,
defaulted when state IS in list = hidden for those states).
Classifier raises `POSSIBLE-CONDITIONAL-HIDDEN` flag — you confirm Business or not.

## Outputs

| File | Contents | Written when |
|---|---|---|
| `{prefix}_System_Defaults.csv` | Rules classified as System | Always |
| `{prefix}_Business_Defaults.csv` | Rules classified as Business | Always |
| `{prefix}_Review_Defaults.csv` | Rules needing human decision | Non-empty only |
| `{prefix}_Gaps_Report.csv` | ODM-only and Direct-only gaps | Non-empty only |
| `{prefix}_Agent_Consumer_Diff.csv` | Fields with different defaults per flow | Non-empty only |
| `{prefix}_Field_Duplication_Issues.csv` | Duplicate field pairs (base + PL_ twin) — **review with product** | Non-empty only |

### Field duplication issues — important, kept separate

Some fields exist twice in the ODM under different names: a base field and a
`PL_`-prefixed twin (e.g. `NumberCarSpace` + `PL_NumberCarSpace`). The non-PL
field typically holds an `OdmDefault` as a word value (`"Two"`) while the PL_
field holds the real typed input (`2` from `ConsumerInput`) — confirmed via the
Policy Data Audit screen.

This is a data-integrity issue, NOT a value-format bug. These pairs need product
review to consolidate to one field. They are written to a dedicated
`Field_Duplication_Issues.csv` — separate from the general Review pile — because
they are important enough to track on their own. Each row includes the UUID for
ODM traceability.

Detected in HQ2 run: `NumberCarSpace / PL_NumberCarSpace` and
`HowManyTimesInOneCalendarYear / PL_HowManyTimesInOneCalendarYear`.

## Key columns in output CSVs

All output files carry the original ODM columns plus these enriched columns:

| Column | Description |
|---|---|
| `Canonical` | Stripped field name used for join (`PolicyData/X` → `X`) |
| `Direct Control Type` | Control type from Direct (authoritative) |
| `Direct Display Rules` | Raw display rules from Direct |
| `Direct Default Value` | Default value as specified in Direct (may differ from ODM) |
| `Implement Value` | **The single authoritative default to actually implement** for this row (see derivation below). This is the column downstream SQL/RE generation reads — not `Default Value`. |
| `Value Status` | Why `Implement Value` holds what it does: `OK` / `EMPTY (clear field)` / `COMPUTED` / `CONDITIONAL` / `RESOLVED (user)` / `PARSE-ARTIFACT`. Tells QA how much to trust the value and which rows a human signed off on. |
| `Direct LOBs` | LOBs from Direct (cross-check against ODM LOBs) |
| `Classification` | System / Business / Review |
| `Classification Reason` | Why this classification was assigned |
| `Flags` | Pipe-separated special flags (see below) |

## Special flags — stop and ask on these

### POSSIBLE-CONDITIONAL-HIDDEN
Display Rules have conditions (AND/OR/IF/state) and the default value also
references conditions. The field is likely hidden for exactly the cases where
this default applies — like `DogsBreedsSelection` (visible when state NOT in
[AZ,CO,...], defaulted when state IS in [AZ,CO,...] = hidden for those states).

**Action:** Confirm whether the field is hidden for the conditions the default
applies to. If yes → Business. If no → leave in Review for further decision.

### RADIO-CONFLICT
ODM has a default value for a field that Direct classifies as Radio or Segmented
Controls. ODM treats radio buttons as checkboxes — Direct is the source of truth.

**Action:** (1) Should this default exist in RE at all? (2) Is the field ever
hidden? If hidden → Business. If never hidden → needs separate decision.

### CONTROL-TYPE-CONFLICT
ODM's `FieldControl` attribute and Direct's `Control Type` column disagree.
Direct wins per convention, but verify.

**Action:** Check the actual UI. Confirm which control type is correct.

### ODM-ONLY
Field has an ODM default rule but does not appear in the Direct at all.

**Action:** Verify the field is in scope. If it's an internal system field
not shown in the interview, classify manually. If it shouldn't exist, flag for cleanup.

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

ODM `Field Name` → strip `PolicyData/` prefix → match to Direct. The match tries
**multiple Direct name columns**, not just one, because a field may be named
differently across them:

1. `Canonical Name`
2. `Pre-fill Element` (with `PolicyData.` prefix stripped)
3. `GetQuote_DD`
4. `Platform Field`

The ODM field name is matched against all four (case-insensitive). This resolves
the common case where ODM uses the short name and Direct's `Canonical Name` uses
a numbered or prefixed variant (e.g. ODM `HomeSkirted` → Direct `IsTheHomeSkirted`
via the GetQuote_DD column). Adding the multi-column join resolved 75 previously
unmatched fields in the HQ2 run.

### Confirmed mapping decisions

User-confirmed field mappings are stored in `{prefix}_Field_Mapping_Decisions.csv`
and loaded on every run:
- **SAME FIELD** decisions remap the ODM name to the Direct canonical so the join succeeds
- **DIFFERENT FIELD** decisions are suppressed from the spelling report so they're not re-flagged

This file is the permanent record — once a spelling/near-match pair is confirmed,
it never needs re-asking. Commit it alongside the other outputs.

### Parent-child multi-select fields

Some ODM fields are `...Multi[]` children of a boolean parent (e.g.
`BurglarAlarmTypeMulti[]` is the checkbox child of the boolean parent
`BurglarAlarm`; `FinancialHardshipsMulti[]` is the child of `PL_Foreclosure`).
These map to the single Direct field — confirmed same field in the mapping decisions.

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


## Fixes applied (Issue #11)

- **(a) Control-type synonyms** — `normalize_ct` maps semantic synonyms and messy
  multi-word labels to a canonical token (`numeric` ≡ `Input field (Numeric)`;
  `Date Field with calendar` → `date`; `Number Stepper` → `stepper`), removing
  false `CONTROL-TYPE-CONFLICT`. Genuine widget mismatches still surface.
- **(b) Computed-date defaults** — checked before control-type logic; formulas
  (`today's year - N`, `PurchaseDate month/15/year`) and cross-field date copies
  are tagged `COMPUTED-DATE-DEFAULT` and routed to Review.
- **(c) Disabled=true display-locks** — parser now extracts `Disabled`; classifier
  routes `Disabled=true` rows out of defaults with `DISABLED-DISPLAY-LOCK`.
- **(e) Enum-label normalization** — `--enum-norm PGR_Enum_Label_Normalization.json`;
  field-scoped ODM-value→Direct-label map (`cov5000`≡`$5k`, `true`≡`Yes`). SAFE-only:
  no generic prefix stripping; genuine code→label needs an explicit map entry or the
  AppData enum table. Adds a `Default Match (norm)` column and normalizes the
  Agent/Consumer diff.
- **Spelling suggester** — never proposes merging `PreDateOccupied1`/`DateOccupied`
  or `PreEffectiveDate1`/`EffectiveDate` (a `pre` prefix changes field meaning).

## FINAL build + overrides + merge (2026-07-15)
- **Condition-aware flow merge:** collapse ONLY rules identical except the `Claim:InterviewFlowType_(Agent|Consumer)`
  flag (same field + default + flow-agnostic condition). Never merge on default value alone. Keep `Merged Rule Count`
  + `Merged UUIDs`; sum must equal the input rule count (proof of no loss).
- **Two extra buckets:** `Refactor` (remove from interview) and `Investigate` (need carrier info) — no default classification.
- **Field overrides:** update family (heating/electrical/plumbing +Year) → Business (value) / System (cleaning);
  DogsBreedsSelection → Business; PAA Carrier Questions page → Business; PLDfForm → Business.
- **Coverage** column: BOTH / ODM-ONLY / DIRECT-ONLY (Direct↔ODM match via name aliases in Field_Mapping_Decisions).
- **Flags:** VALUE-MISMATCH (Direct wins), MISSING-IN-DIRECT-CONSUMER, CARRIER-DEPENDENCY, CONTROL-TYPE-CROSS-FLOW.

---

## Classification buckets, exclusions & FINAL build (reusable methodology — added 2026-07-15)

This section is the reusable layer (there is deliberately **no consolidation script** — the FINAL merge is
tenant-specific and done by command, guided by this doc).

### Classification buckets
- **Business** — value default sent to the business/DB layer. Includes concrete enum/numeric/boolean values,
  computed defaults (date arithmetic, YearsAtAddress bands), and cross-field/mapped value copies.
- **System** — cleaning rules (empty/blank default), stage-init rules (e.g. `*=Initialized`).
- **Refactor** — field being removed from the tenant interview. Keep in the list (tagged) so carriers depending
  on it can be verified before removal; do not build as an RE default.
- **Investigate** — needs external carrier/vendor info to decide.

### Exclusions (route to a reference CSV with UUID + reason — NOT into the FINAL)
- **Dead rule** — a flag-gated branch that can never fire (flag is always the opposite state), a rule keyed on a
  retired field being *known*, an option that doesn't exist (e.g. `is one of {Apartment}` when Apartment is
  irrelevant), or an NA-only condition.
- **Display-lock** — `Disabled=true` + self-referential default (field = itself). It re-shows an existing value
  greyed out; it is relevancy, not a default.
- **Parse-artifact** — default value == a field named in the same condition (e.g. `NunMajorViolationsLast3Years`,
  `BPPComputerEquip`, `FaultClamisNum3Y`). Do not migrate; verify raw `.m`.
- **Self-referential** — default == the field itself → irrelevant, ignore.
- **Irrelevant-to-tenant** — field not used by this tenant (confirm with product).

### Flag handling
For each `ba_*` / feature flag, get its LD state (all-envs) and its ODM reference direction:
- Flag always ON  → rules gated `flag=true` are LIVE; rules gated `flag=false` are DEAD. Implement flag TRUE, add to cleanup tracker.
- Flag always OFF → the reverse. Implement FALSE, add to cleanup tracker.
Record every flag in `PGR_Flags_To_Clean.csv` with: disposition, always-state, code-ref, ODM-ref, user-story, action.
Flag states are baked into the parser output, so flag config only matters on a **re-parse**.

### FINAL build (by command)
1. Combine classifier outputs (System/Business/Review) + Direct-only gaps into one table.
2. Condition-aware flow merge: collapse ONLY rules identical except the `Claim:InterviewFlowType_(Agent|Consumer)`
   flag. Keep `Merged Rule Count` + `Merged UUIDs`; the UUID sum must equal the input rule count (proof of no loss).
3. Coverage = BOTH / ODM-ONLY / DIRECT-ONLY (Direct↔ODM matched via name aliases, incl. `PL`-prefix twins).
4. Walk Product-Review with product in batches of ~15; write decisions into the FINAL (Classification + Reason).
5. Route exclusions to the reference CSV. **Reconcile**: every input UUID must appear in FINAL or the reference.
6. **Derive `Implement Value` + `Value Status`** for every row (this is the base info core downstream code-gen consumes).

### Implement Value derivation (the actual default to migrate)
`Default Value` (ODM) mixes clean literals, enum codes, and computed expressions; `Direct Default Value` mixes labels
and conditional prose. Neither alone is implementable. Derive one authoritative `Implement Value` per row:

- **Manual override** — a recorded user/product decision wins over both. Status `RESOLVED (user YYYY-MM-DD)`.
  (Progressive so far: `NumberOfMortgagees`=0, `NumberOfChildren`=0, `CurrentPersonalHomeownerCarrier`=Other, `SupplementalHeating`=0.)
- **Parse-artifact** — if the ODM default equals a field name (`NunMajorViolationsLast3Years`, `BPPComputerEquip`,
  `FaultClamisNum3Y`): blank it, status `PARSE-ARTIFACT — do not migrate; verify raw .m`.
- **Empty** — ODM and Direct both blank (System clear-field rules): value is empty; status `EMPTY (clear field)`. Empty IS the value.
- **ODM blank, Direct present** — use Direct if it's a clean literal (`OK (Direct)`); if Direct is prose, blank + `CONDITIONAL (Direct)`.
- **Computed** — ODM value is a formula or cross-field ref (`today's year - 50`, `PLYearBuilt`, contains `(` or `/`,
  arithmetic, date-ish): keep the expression as `Implement Value`, status `COMPUTED`. A computed default cannot be a
  static DB default — it belongs in RE logic even if the row is classed Business.
- **Conditional prose** — ODM value is multi-word / contains if/then: keep as-is, status `CONDITIONAL`.
- **Clean literal/enum** — store the **ODM enum code**, not the Direct human label, even when they agree (`CompleteUpdate`,
  not "Complete Update"). Compare via `PGR_Enum_Label_Normalization.json` + a space/case-insensitive squash, matching field
  keys with `PL_`/`PL_F###_`/`[]`/path stripped. Status `OK` (or `OK (enum; Direct describes branching)` when Direct is prose).
- **Genuine ODM≠Direct disagreement** (both clean literals, not enum-equivalent) — do NOT auto-pick. Keep the ODM enum
  and flag `REVIEW (ODM=x vs Direct=y)`; surface to user/product for a decision, then convert to a `RESOLVED` override.

Never fabricate a single literal for computed/conditional rows. `Implement Value` blank + a COMPUTED/CONDITIONAL status
is the correct output there — the logic lives in `Field Conditions`.
