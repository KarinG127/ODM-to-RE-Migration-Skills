# Progressive ODM→RE Migration — Progress Tracker

**Last updated:** 2026-07-15
**Purpose:** Single source of truth for where the migration stands. Read this first each session.

> Record every decision in the Decisions Log so it never has to be re-derived.
> This file + the CSVs travel together.

---

## ▶ RESUME HERE (handoff — read before doing anything)

**Stage:** Defaults (1 of 4). **FINAL corrected + all decisions captured in an overlay.** Direct regenerated from product's
updated files. Next hard task: script the consolidation so reruns are reproducible (Issue #20). See `HANDOVER.md`.

**Authoritative files (travel together):**
- `HANDOVER.md` (read first) · `PROJECT_PROGRESS.md` (this file) · `OPEN_ISSUES.md`
- `PGR_Defaults_FINAL_corrected.csv` — THE deliverable (544 lines; #1–#5 + batch applied).
- `PGR_Defaults_FINAL_corrected.csv` (526) is THE source of truth (Classification + Classification Reason). NOTE: the overlay JSON and the consolidation-script idea were both DESCOPED (one-time migration, tenant-specific merge-by-command). Product Outcome column retired.
- `PGR_Defaults_Excluded_Reference.csv` (26) — dead/stage/display-lock/parse-artifact/irrelevant rules + UUIDs.
- `Progressive_Direct_Master.csv` — regenerated from updated Direct (PAA v22 / HQX 12.9, 515 rows).
- `PGR_Flags_To_Clean.csv` (9) · `PGR_Defaults_Stage_Only_Removed.csv` · `PGR_Defaults_Field_Mapping_Decisions.csv` (8 name aliases).

**Current numbers (FINAL):** **526 rows**; classification **Business 289 · System 143 · Refactor 70 · Investigate 13 · Product-Review 11** (0 unclassified). All 570 ODM UUIDs reconcile: 544 in FINAL + 26 in PGR_Defaults_Excluded_Reference.csv. Only remaining review = 11 Progressive_Preferences rows.
Classification: **Business 184 · Product-Review 171 · System 141 · Refactor 27 · Investigate 21 · 0 unclassified.**
(552→544: dropped 2 ReplacementCost, 4 stage-only, 1 PreEffectiveDate dup, 1 Houseoccup corrupt, 1 Electrical bug; +2 Houseoccup split.)

**Merge rule:** collapse ONLY rules identical except the flow flag (same field+default+flow-agnostic condition).
Different conditions never merge. Rationale: ODM worked per-stage (same default can appear twice); RE sends all
at once, so stage-duplicate twins are safe to merge.

**Two new classification buckets this session:** `Refactor` (remove from PGR interview) and `Investigate`
(need carrier info). These rows get NO default classification.

**Next session (in priority order):**
1. **Build `odm_defaults_consolidate.py`** (Issue #20) — script the documented FINAL merge + field-overrides + Coverage + Refactor/Investigate, consuming the overlay. Validate against `PGR_Defaults_FINAL_corrected.csv`.
2. **Rerun end-to-end** (classifier → consolidate → overlay) on the updated Direct so the 46 Direct-affected Product-Review rows re-resolve (Issue #24).
3. **Field-by-field** through the resulting Product-Review WITH the user; each answer → overlay by UUID.
4. Refactor (27) / Investigate (21) carrier verifications (Issue #17).
5. Flags (Issue #21): add the 3 flags to `progressive_config.json`; interview-JSON / ODM cleanup for ba_fl-carriertrue & ba_tmp_preference_redesign_cr618.
6. Start Stages 2–4 (Validation, Relevancy, Stages).

**Conventions:** Direct wins on default mismatch · merge only identical-condition flow twins · product decides,
tag eng calls "pending product confirm" · **overlay (`PGR_Defaults_Decisions.json`) is the single source of product decisions; Product Outcome retired** · ODM currently untouched (no re-parse needed) · don't edit the classifier skill without approval.

---

## Session changelog — 2026-07-15 (session 2 close-out)

- **Product-Review walk COMPLETE**: 171 → 11 (only Progressive_Preferences1/2 remain, marked PENDING REVIEW). ~150 rows reclassified via product decisions in batches of ~15.
- **All 570 ODM rules reconciled**: 544 classified in FINAL + 26 in PGR_Defaults_Excluded_Reference.csv (incl. 4 early/pre-chat drops recovered: ElectircalUpdatedYear bug, PL_Houseoccup artifact, PL_VaultedCeilings & PL_CrownMolding pre-chat hide-vaulted-and-crown exclusions).
- **Overlay JSON + consolidation-script DESCOPED** (Issues #6, #20 closed) — FINAL CSV is the single source; reusable layer is skill docs.
- **Date cluster** resolved (Issue #3): computed date defaults→Business; EffectiveDate display-lock routed out.
- **Flags tracker → 10** (added ba_yearbuild-default-date; corrected ba_Condo_Redesign to always-TRUE). Config pending future re-parse only.
- **Carrier RC1 review** (Issue #9) resolved: enum(false)=UI(No); ODM/Direct values stand.
- New HANDOVER.md written for the next chat.

---

## Session changelog — 2026-07-15 (continuation / session 2)

- **Review findings addressed #1–#5** + batch: RC dropped; ActualCashValue→Business (cross-field); LivingTime→PL_LivingTime Business; DwellingOccupancy→Business; Bankruptcy→Business; PreEffectiveDate1→Business (deduped); PL_Houseoccup split System/Business (corrupt row dropped); ElectircalUpdatedYear bug `01b5f03f` dropped + 3→Business; 4 stage-only rows removed to `PGR_Defaults_Stage_Only_Removed.csv`; PlumbingUpdated confirmed ODM twin.
- **Overlay created** `PGR_Defaults_Decisions.json` — 389 UUID overrides harvested + explicit decisions. Closes most of Issue #6.
- **Flags:** +`ba_fl-carriertrue` (FALSE), +`ba_abtest-naming-convention` (TRUE), +`ba_tmp_preference_redesign_cr618` (TRUE) → tracker now 9 (Issue #21).
- **Direct regenerated** from product's updated files (PAA v22 / HQX 12.9); found 46/171 Product-Review rows newly match (Issue #24).
- **KEY FINDING:** FINAL build is unscripted — logged as HIGH Issue #20; consolidation script is the next build.
- **Product Outcome retired** — overlay is the single source going forward.

---

## Session changelog — 2026-07-15 (session 1)

- **Full rerun** from raw ODM (1692 files); reconciled against last session's FINAL — 0 defaults lost logically
  (5 UUID diffs explained: 3 dead always-ON false-branches, 2 ApplicantYearofBirth = table move / new UUIDs).
- **Classifier skill fixes applied (Issue #11 a/b/c/e)** + spelling guard. Skill docs updated.
- **Parser:** main output is DefaultValue-only; relevancy/stage split to `_Relevancy_Stage_Rules.csv`; dead/ignored
  archive `_Dead_Ignored_Rules.csv` (per-UUID reason); `Disabled` attribute extracted.
- **New classification logic:** Carrier Questions page → Business; PLDfForm (92) → Business; checkbox both-flow;
  flags VALUE-MISMATCH (Direct wins) / MISSING-IN-DIRECT-CONSUMER / CARRIER-DEPENDENCY / CONTROL-TYPE-CROSS-FLOW.
- **Name mappings (8)** encoded; `F1832_PreEffectiveDate1` renamed to `PreEffectiveDate1`.
- **Field overrides:** update family → Business (cleaning→System); DogsBreedsSelection → Business;
  Refactor set (Burglar/Fire/MitRoof/NumberOfChildren/HomeNewPurchase/TriagePriorCarrier);
  Investigate set (MitSecWaterResis/DealershipPurchase/Swimming/Trampoline/Pool/AdditionalStructures/NumberOfChildernsUnder18).
- **Config:** ba_hide-vaulted-and-crown + ba_hide-current-carrier → ALWAYS_TRUE_CLEANUP; flags-to-clean now 7.
- **Product docs reconciled:** MASTER_2 authoritative, merged with old (5 recovered outcomes).
- **FINAL rebuilt** in merged old-file style + condition-aware flow merge; Coverage + Prior Classification + Changed flag.

---

## ⚠️ Read this first — the persistence gap

Classification/merge decisions made in chat are **not automatically saved** back
into the pipeline. Until that's fixed (Open Issue #6), THIS FILE is the
authoritative record of decisions — not any regenerated CSV.

## 📦 FINAL OUTPUT SPEC — build LAST, after review is complete

The current `PGR_Defaults_Classified.csv` is a WORKING decision log (field + free-text
label only) — NOT the deliverable. The real final output is to be built ONCE the step-3d
review is done. It must be:

**`PGR_Defaults_FINAL.csv` — ONE ROW PER RULE (not per field), keyed by UUID.**
Columns:
- UUID, Field, AppData Canonical  (identity)
- Flow, LOBs, Visible, Page  (scope)
- Full Condition, Default Value  (the actual rule)
- Classification: System | Business | Product-Review | Dead
- Classification Source: confirmed-decision | auto-triage | archive
- OperationSource (supportsite audit): DB/Business default → "AdminDefault" (more values TBD)
- Source File (.m path)

Plus a SUMMARY: counts of System / Business / Product / Dead, and confirmed vs proposed.

Universe = 571 live DEFAULT rules (933 total minus 362 relevancy). 636 rules already in
the dead/ignored archive belong in the Dead bucket / archive cross-ref. Classification is
PER-RULE: one field (e.g. PLNumberOfUnits) can have rules in System, Business AND Dead.

## 🔁 RECURRING PATTERNS — apply these to every field

Principles learned from real fields; check these before analyzing a new one.

### Control type is PER-FLOW — always check both Direct columns
The Direct master has TWO control-type columns: **`Control Type`** = PAA/agent,
**`HQ2 Control Type`** = HQX/consumer. The same field is often a **checkbox for
consumer but Segmented Controls for agent** (e.g. the AdditionalStructures family,
PL_HeatedByOil). NEVER infer control type from ODM data alone — read both Direct
columns. Classification can therefore differ by flow: consumer-checkbox side →
System; agent-segmented side → surface for review. "Boolean value" does NOT imply
checkbox.

### Missing-from-Direct — state WHICH Direct (PAA vs HQX)
When flagging a field missing from Direct, always specify per flow in the
`Direct Reference` column, format: `PAA/agent: present (CT) | HQX/consumer: MISSING`.
A field is frequently asked in one flow and hidden-with-default in the other.
(e.g. NonSmoker/GatedOrLimited/ResHeldTrust = agent Segmented, missing consumer;
PrimaryHome = consumer Segmented, missing agent.)

### Retired fields in conditions — "is unknown" is always TRUE
When a RETIRED/irrelevant field (no longer in the interview) appears in a condition,
it is never set, so:
- `RetiredField is unknown` → **always TRUE** → KEEP the rule, treat that clause as true.
- `RetiredField is known` → always FALSE → dead rule.
- `RetiredField is <value>` → never matches → dead rule.
Known retired fields: `TriagePriorCarrierHomeowners`, `HomeNewPurchase` (both also need
Direct correction — flagged to product). Registered in progressive_config.json → retired_fields.
Always check the exact clause type before killing a rule that references a retired field.

### Dead rules from always-true / retired flags
Some ba_ flags are ALWAYS ON in all environments. A rule whose condition requires
such a flag to be FALSE is a DEAD rule → ignore (don't classify). Known always-true:
`ba_floor-questions-segment`, `ba_no-of-units` (both should be cleaned from code).
Also dead: Consumer 1.0 (`ba_LightApi_False` true, OR `ba_LightApi_True` FALSE — both
phrasings mean not-HQX-2.0) and Agent 1.0 (`ba_odysseyapi_False`) gated rules — old
flows, not relevant now. Dead/ignored rules logged in `PGR_Dead_Ignored_Rules.csv`.

### Orphaned cleaning logic (option no longer on platform)
A cleaning rule that clears a field when it equals an option the platform NO LONGER
HAS (e.g. PLHeatingType="Other", PLTypeOfDwelling="Apartment") is orphaned → flag to
product ("Orphaned Cleaning Logic" category), don't classify as System. The option's
absence means the rule can't meaningfully fire.

### Carrier Questions page + RC1 default (AGENT flow)
Some fields live on the **PAA Carrier Questions** page (one sheet in the PAA Direct).
That sheet has a column per carrier — a "v" or the relevant LOB marks which carrier a
question applies to — plus a **"Value for RC1 submission"** column. RC1 = the first
stage of the Quick Quote section. The business default for these agent carrier-question
fields = the "Value for RC1 submission" value, so the question can surface on the Carrier
Question page after the user selects a carrier (if relevant to that carrier). When an
AGENT carrier-question default is missing, that RC1 value IS the intended business default.
(Example: CurrentPersonalHomeownerCarrier is relevant for StillWater HO3 & DF only.)
Open question to product: agent flow needs these defaults — but why does the CONSUMER
flow also get a default for carrier questions?

### OperationSource (supportsite audit field) — for the FINAL output
Each default carries an audit field "OperationSource" on the supportsite. Rule so far:
- Default sourced from the DB → OperationSource = **"AdminDefault"**.
(More OperationSource values may come later; add them here as learned. The FINAL output
should carry an OperationSource column derived from classification: Business/DB → AdminDefault.)

### Parent-child cleaning rules
A rule that sets a CHILD field to false/empty when its PARENT is answered false
(e.g. BusinessOrDaycare=false when BusinessOnResidencePremises is false and child
was true) is **cleaning logic → System**, not a business default.

### Triage-stage duplication (ODM two-table pattern)
**Triage is an AGENT-ONLY stage/page.** In ODM, a field shown in both agent and
consumer flows often appears as TWO decision tables — one under `Triage/` and one
under the consumer page (e.g. `Exterior/`). This is the normal ODM footprint, not a
bug. **Test:** if all rules are identical across the two tables (same condition +
value), RE likely needs only ONE set — RE models stage/page separately from default
logic.
⚠️ **DO NOT auto-collapse. ALWAYS surface it for the user to decide.** Even when the
two tables look identical and Triage is involved, flag the specific field to the user
(and, if they direct, to product) and let them confirm before any rule is dropped.
The RoofUpdatedYear collapse was a per-field USER decision — it is NOT standing
permission to drop future Triage duplicates automatically. Report every additional
field with this pattern so the user knows about it.
(First seen: RoofUpdatedYear — 36 rules = 18 unique × 2 tables; user decided to collapse.)

### Duplication vs dense logic (verify on FULL conditions)
Shared long condition prefixes can make distinct rules look identical. Always diff
the FULL condition + value before calling something duplication. (PLDfForm looked
like 42 duplicate DP3 rules but was 42 distinct state/occupancy/band mappings — kept
all. RoofUpdatedYear looked similar but WAS true 1:1 duplication — collapsed.)

### -99 sentinel fragments
Conditions like `- 220.1 is more than -99` are parser artifacts (always-true
sentinel), not real logic. Safe to ignore; note but don't escalate.

---

## 📌 CONVENTION — ONE product-review file only

There is exactly **ONE** product-review output: **`PGR_Product_Review_MASTER.csv`**.
Every item needing product input goes here — never create separate per-topic
product CSVs again. Distinguish item types with the **`Category`** column
(e.g. Default Value Disagreement, ODM Default — No Direct Reference, Name Alignment,
Date Field — Computed Default, Duplicate Rule, Rule Review). Each row carries a
source reference: **ODM Reference (UUID)** for ODM-sourced items, **Direct Reference**
(Field ID + sheet) for Direct-sourced items. When a new product question arises,
APPEND a row to this file — do not spin up a new CSV.

---

## The 4 migration stages — top-level status

| Stage | Description | Status |
|---|---|---|
| 1. Defaults | Default values per field/LOB/flow | 🟡 In progress — see Defaults Workflow below |
| 2. Validation & Kickouts | Field validations, hard stops | ⚪ Not started (parser exists) |
| 3. Relevancy | When/whether a field displays | ⚪ Not started |
| 4. Stages | Which stage/page a field belongs to | ⚪ Not started |

Legend: 🟢 done · 🟡 in progress · 🔴 blocked · ⚪ not started

---

## Stage 1 — DEFAULTS WORKFLOW (the agreed 8-step plan)

This is the sequence we're executing, defined 2026-07-07.

| Step | Description | Status | Output |
|---|---|---|---|
| 1 | Extract all defaults from ODM | 🟢 DONE | `PGR_Defaults_Defaults.csv` — 933 rules (571 Default + 362 Relevancy) |
| 2 | Extract all defaults from Direct | 🟢 DONE | `PGR_Direct_Defaults.csv` — 45 real; `..._ProseLogic_HOLD.csv` — 45 held |
| 2b | **Parse RE ApplicationData as canonical name authority** | 🟢 DONE | 348 AppData props + 118 enums; `PGR_AppData_Name_Mappings.json` |
| 2c | **Parse ProgressiveCommonRelevancy.cs** | 🟢 DONE | 165 relevancy fields + 44 intentionally-removed |
| 3 | Merge ODM+Direct, find gaps | 🟢 DONE (rebuilt) | `PGR_Defaults_Merged_v2.csv` — 584 rows |
| 3b | Resolve value-mismatches | 🟢 DONE | 5 normalized + 5 → product review |
| 3c | Review DIRECT-ONLY gaps | 🟢 DONE | All false gaps resolved via AppData; 7 real Direct-only defaults remain |
| 3d | Review ODM-ONLY rows | 🟡 In progress | 519 rows / 111 fields. Blank-canonical (40 fields) DONE; resolved-canonical duplication NEXT |
| 4 | Build ONE unified unique-defaults CSV | ⚪ TBD | dedup depends on 3d; use AppData canonical names |
| 5 | Align on System-vs-Business logic | ⚪ TBD | conversation + confirm rules |
| 6 | Test classifier on examples, ask on unclear | ⚪ TBD | — |
| 7 | Run classifier → System + Business CSVs | ⚪ TBD | `PGR_System_Defaults.csv`, `PGR_Business_Defaults.csv` |
| 8 | User directs next steps | ⚪ later | — |

### Merge results — REBUILT v2 (step 3, corrected)
The first merge (`PGR_Defaults_Merged.csv`, 591 rows) used a **single-column** join
(Canonical Name only) and produced false gaps. Rebuilt using the classifier's
**4-column join** (Canonical + GetQuote_DD + Pre-fill + Platform) anchored on
**AppData canonical names**. Use `PGR_Defaults_Merged_v2.csv` going forward.

| Match Status | Rows | Distinct fields | Meaning |
|---|---|---|---|
| ODM-ONLY | 519 | 111 | ODM has default, Direct doesn't (duplication lives here) |
| BOTH | 52 | 23 | Default in both sources |
| DIRECT-ONLY | 9 | 7 | Genuine Direct-only business defaults (GatedOrLimited, ResHeldTrust, NonSmoker, BuiltOnSlope, PLAllPerilsDeductible=1k, PLPersonalLiability=300k, ReplacementCost) |
| DIRECT-ONLY-NOAPP | 4 | 1 | Pre* helper fields with defaults, not yet in AppData |

Old→new shift: BOTH 18→23 fields (+13 matches recovered), ODM-ONLY 155→111
fields (−44 phantoms), DIRECT-ONLY 15→7 real fields. Confirms the 20 original
"gaps" were naming artifacts, not missing defaults.

### Step 3d progress — ODM-ONLY breakdown
ODM-ONLY (519 rows) splits into two groups:
- **Blank-canonical (106 rows / 40 fields) — ✅ DONE.** ODM fields that didn't
  resolve to AppData. Categorized in `PGR_BlankCanonical_Categorization.csv`:
  - Address-sync (18 fields): `Xxx/Field` path notation; keep as address cross-copy defaults.
  - Cleaning (8): empty default + hidden → System.
  - Checkbox-none (4): `_None` / true-false hidden toggles.
  - Drop stage-only (1): `(Stage-only rule)` — not a default.
  - UI-only exclude (2): Progressive_Preferences1/2.
  - Ignore (1): OtherProductType (removed in Direct).
  - Product review (6) → `PGR_Product_Review_MASTER.csv` (category: ODM Default — No Direct Reference): ConstBrickVeneerPct,
    PLSwimmingPoolType, CustomFields/AddressChanged, HowManyTimesInOneCalendarYear,
    NumberOfChildren, SwimmingPoolSafety.
- **Resolved-canonical (~413 rows / ~90 fields) — 🟡 IN PROGRESS.** Fields that DID
  map to AppData but have no Direct default. Where per-field duplication lives.
  Distribution: 51 fields = 1 rule, 35 = 2-3 rules, 20 = 4-9 rules, 5 = 10+ rules.
  - **PLDfForm (92 rules) — ✅ DECIDED: Business (DB/lookup table).** Analysis proved
    it's NOT duplication: 92 distinct state+occupancy+premium-band mappings selecting
    the DF form (DP1_Basic/DP3_Special/HO10). 0 exact dupes, 0 conflicts. Shared gate
    (PLTypeOfDwelling≠MFH + feature AMSuitDwellingFireSubmissionODM) is a table
    precondition. All rules kept.
  - **Heavy-hitters (10+ rules) — ✅ ALL DONE:**
    - PLDfForm (92) → Business (DB), kept all — genuine state matrix, not duplication.
    - RoofUpdatedYear (36) → Business (DB), collapse to 18 (Triage dup dropped, user-decided).
    - DateOccupied (16) → product (date field, computed default).
    - IsMailAddress (12) → product (all 12; address-comparison logic to confirm).
    - NumberOfChildernsUnder18 (10) → product (value disagreement, ODM 0 vs Direct 1).
  - **Remaining: ~20 mid-size fields (4-9 rules) + ~51 single-rule fields — 🟡 IN PROGRESS.**
    Auto-triage run on 104 remaining fields (established patterns). Checkbox batch
    re-verified against Direct PAA/HQ2 control types (critical fix — 16 of 41 were
    NOT plain checkboxes). Results so far in `PGR_Defaults_Classified.csv`:
    31 System + 5 Business decided this batch.
    - 25 confirmed true checkboxes → System.
    - SPLIT fields (consumer checkbox / agent segmented): consumer side → System;
      AdditionalStructures Deck/Pool/HotTub/Trampoline, PL_HeatedByOil (business for
      specific hidden states).
    - BusinessOrDaycare: 4 rules — 3f0fea93 & 244590e0 & a1b752a3 → Business,
      8592a909 → System (parent-child cleaning). a1b752a3 also → product (verify need).
    - NonSmoker, PrimaryHome → Business (hidden default) + product (missing from Direct).
    - GatedOrLimited, ResHeldTrust → product (consumer default but missing HQX Direct).
    - ElectricCircuitBreaker, AnimalsOnThePremises_None, PLHaveAnyLosses → product.
    - **REVIEW fields: ✅ ALL 39 DONE.** Results in `PGR_Defaults_Classified.csv`.
      **STILL TODO before final output:**
      1. Direct-only / prose-logic defaults (Issue #16, HIGH) — 🟢 the 9 held HOLD-file
         fields resolved 2026-07-12 (see Decisions Log). Any remaining prose-logic beyond
         those 9 still to sweep. YearsAtAddress proved a field can have a dead ODM rule
         but a live Direct-only default.
      2. ~23 single-rule / 2-3-rule ODM-only fields — 🟢 ALL CLASSIFIED 2026-07-12
         (see Decisions Log). 17 clear-when-not-applicable → System; PL_PoolType → System
         (+ product consolidation Q); BuiltOnSlope → Business (agent carrier question, FC1);
         InsideCityLimits → Product (no Direct ref). Step 3d is now COMPLETE.
      3. Then build `PGR_Defaults_FINAL.csv` (see FINAL OUTPUT SPEC). ← NEXT
  - **Lesson:** verify distinct-vs-duplicate on FULL conditions before calling
    something duplication — shared condition prefixes can hide real differences.

### Merge design decisions (v2)
- **Name authority:** RE ApplicationData property names are canonical. Every ODM
  and Direct field resolves to an AppData property before matching.
- **Join key:** 4 Direct columns (Canonical / GetQuote_DD / Pre-fill / Platform)
  → AppData canonical + Flow (ODM `Both` matches either Agent or Consumer).
- **Scope:** AppData limited to PL Home (Homeowners + PL_Common + All_Lobs shared).
  Ignore all CL, PersonalAuto, RV, ClassicCar, Motorcycle, carrier-specific WC/auto.
- **Row grain:** ODM rows kept expanded; matching Direct value attached to each.
- **Source of truth:** keep BOTH values side-by-side, flag mismatches for review.
- **New rule:** any Direct field with no reference in AppData AND no reference in
  ProgressiveCommonRelevancy → open a bug under the Relevancy Migration task.

---

## Earlier work — Control-Type-Conflict pass (prior sub-thread)

Before the 8-step workflow was defined, we worked the classifier's Review pile
(from last session's `PGR_Review_Defaults.csv`). Decisions from that pass still stand:

| Field | Decision | Status |
|---|---|---|
| PLFloorNumber | Business (hidden unless PLHighRiseCondo=Yes) | 🟢 |
| PurchaseDate / DateOccupied / EffectiveDate | Product review (all date rules) | 🟢 routed |
| PL_NumberOfFloors | Review — 2 corrupt defaults parked | 🟡 |
| PreDateOccupied1 | Separate field, classify alone | 🟢 noted |

Note: date fields verified faithful to raw ODM this session (defaults are genuine
computed values / FORMAT STRING expressions, not parser bugs).

---

## Decisions Log — permanent record

### 2026-07-12 (Issue #7 tail — final ~23 ODM-only fields classified → step 3d COMPLETE)
- **17 clear-when-not-applicable → System** (established cleaning pattern, empty default +
  hidden + guard): CoFirstName, CoLastName, CoMiddleName, CoDateOfBirth, SelectRelationshipToClient
  (AnyAdditionalInsured=false); SSN, CoSSN (SSN-removal); OilTankLocation, PL_TrampolineInFence,
  PL_NettedTrampoline, TypeGarageCarport, TypeOfBusinessDD, PreviousAddress, ReasonVacant,
  PL_TypeFireplaces, PLPersonalProperty, PL_BasementFinish, YearsWithPriorCarrierHome,
  PL_RoofUpdateYearRange.
- **PL_PoolType → System** (cleaning always) + product consolidation Q retained (why both
  PLSwimmingPoolType and PL_PoolType).
- **BuiltOnSlope → Business.** User: question shown only in Consumer flow; for Agent it is a
  carrier question, so the default is a Business default, FC1 stage only.
- **InsideCityLimits → Product** (no Direct reference; address-adjacent). Added to product master.
- UUIDs for every rule recorded in the decision log; they carry into `PGR_Defaults_FINAL.csv`.
**Step 3d (ODM-ONLY review) is COMPLETE. Next: build the FINAL per-rule output.**


Resolved the 9 held prose-logic fields from `PGR_Direct_Defaults_ProseLogic_HOLD.csv`:
- **DogsBreedsSelection[]** → Business (state hidden → NoneOfTheAbove; NV + AZ/CO/IL/MN/NY
  merged to ONE rule) + System (no-dogs empty cleaning, 873bfe42). ODM covers it.
- **Bankruptcy** → Business, DIRECT-sourced → DB (AppData ForeclosureOrRepossessionOrBankruptcy
  intentionally-removed; user-confirmed).
- **RoofResponsible** → System (consumer hidden empty, 6766c562) + Business (Agent True if
  TypeOfDwelling=Condominium, DIRECT-sourced). Product flag: name mess (PL_RoofResponsible vs
  RoofResponsible) + flow discrepancy + "changes the LOB" → verify UI-only.
- **ReplacementCost** → DROP, no default (Agent "blank if not data-filled" = prefill-only).
- **LivingTime** → DROP, no default (PL_LivingTime in ODM is only a CONDITION feeding
  OccupancyType default 3dbd8684; user-confirmed).
- **DwellingOccupancy** = OccupancyType (already Business + System); no separate rules.
- **DateOccupied, PurchaseDate** → already in product (date computed defaults); **ElectricalUpdated**
  → already covered (typo-twin of ElectircalUpdated + name-alignment product item). Confirmed, not re-done.

**Issue #4 (PL_NumberOfFloors):** re-confirmed this session, but it was ALREADY resolved on
2026-07-07 (below) with identical conclusions — no change. `ba_floor-questions-segment` cleanup
lives in `progressive_config.json` (business_flags), not a flags CSV.

**RESTORED (was lost when intermediate files were deleted):** NumberOfChildernsUnder18 →
product (value disagreement, ODM 0 vs Direct 1). Re-added to `PGR_Product_Review_MASTER.csv`.

**Housekeeping / de-duplication:**
- `PGR_Defaults_Classified.csv` is now a GENERATED MIRROR of `PGR_ODM_Only_Field_Decisions.csv`
  (the authoritative decision log). They previously overlapped (Classified was a 66-field subset
  of the 69-field ODM_Only) and risked drift. ODM_Only is the master; Classified is the simple view.
- RoofUpdatedYear stays **18 unique rules** (Triage dup collapsed). A "36 rules" note produced
  mid-session was an error and was NOT persisted.
- PLDfForm stays **92 rules, all Business** (per prior decision). Observed 1 empty-default rule
  in the set — flagged for a later quick check whether it is a separate cleaning rule; call unchanged.


### 2026-07-07 (REVIEW complete + retired fields)
**All 39 REVIEW fields classified.** Final batches: person/carrier (6) + Group 3 (3).
- CoMaritalStatus → Business + System cleaning (Direct field-format missing → product).
- Occupation → Business (not in Direct → product).
- CurrentPersonalHomeownerCarrier → Business (OtherStandard consumer) + System cleaning;
  51db66/f51c437 stage-duplicate (Triage/Owners) collapse. Carrier-Questions/RC1 concept
  documented; product Q: why does consumer flow need this default?
- DogsWithBiteHistory → 2 Business (state) + System cleaning + self-ref archived (display-lock).
- TrampolineFenced → Business + System cleaning (not in Direct → product).
- CeilingHeight, PerimeterSecurityDD, PL_OccupiedOrPurchase → Business.
**Retired fields:** TriagePriorCarrierHomeowners + HomeNewPurchase registered as retired.
Key rule (user): retired field `is unknown` in a condition = always TRUE (keep); `is known`
or value-check = dead. Verified TPCH rules were all value/known checks → correctly dead/archived.
HomeNewPurchase = 0 ODM rules but 7 Direct references → product to correct Direct.
**YearsAtAddress correction:** ODM rule dead (TPCH), BUT Direct has a live Consumer prose
default (hide+0 on new purchase) → Business, DIRECT-sourced. Exposed Issue #16 (Direct-only
defaults not yet reviewed — HIGH).

### 2026-07-07 (enum/coded batch — groups 1 & 2, 9 fields)
- **OccupancyType** → Business (hidden enum defaults) + System (empty cleaning); missing consumer Direct (product note).
- **PlumbingType** → Business (hidden).
- **BurglarAlarmType, FireDetectionType** → PRODUCT. Part of parent/child-Multi[]/Type
  triplet; Direct maps to the Multi[] variant (GQ_DD), so plain Type field is orphaned.
- **SelectReasonNoPriorHomeInsurance** → PRODUCT (not in either Direct; still relevant?).
- **DwellingUsage** → Business (derived from OccupancyType) + System (empty cleaning).
- **SprinklerSystemType** → PRODUCT (missing HQX Direct; mostly business: Full when
  SprinklerSystem=true, empty cleaning when false).
- **PLTypeOfDwelling** → 2 Business (ManufacturedHome hidden/not-shown-for-MFH,
  SingleFamilyHouse hidden) + 1 DEAD archived (17042714…4aacccd, ba_LightApi_True false
  = HQX 1.0) + 1 PRODUCT (be5c3cc4…08877be8, clears when "Apartment" — platform has no
  Apartment option → orphaned cleaning).
- **PLHeatingType** → both rules PRODUCT: dc5d37…faf23b (WoodBurningStove when NA — no
  Direct reference confirms this value) + 4397…a5aa7a45 (clears when "Other" — platform
  has no Other option → orphaned cleaning).
New patterns recorded: orphaned cleaning logic, parent/child-Multi/Type triplets,
ba_LightApi_True-false phrasing = HQX 1.0 dead.
**Progress: 23 of 39 REVIEW fields done.**

### 2026-07-07 (progress checkpoint + final-output spec)
Recorded the FINAL OUTPUT SPEC (see section near top): `PGR_Defaults_FINAL.csv`,
one row per RULE keyed by UUID, with full condition/value/scope + Classification
(System/Business/Product/Dead) + Source (confirmed/auto-triage/archive) + summary counts.
To be built LAST, after step-3d review completes. Current `PGR_Defaults_Classified.csv`
is a WORKING log only, not the deliverable.
**Progress:** step 3d review = 7 of 39 REVIEW fields confirmed; 32 remain (grouped in the
workflow section). Universe = 571 live default rules; 636 already in dead/ignored archive.

### 2026-07-07 (ba_no-of-units flag + PLNumberOfUnits finalized)
`ba_no-of-units` = HQX 1.0 (Consumer 1.0) flag, cleaned from code but still ON in
LaunchDarkly; ODM is the only remaining source. Carriers Homesite & AMIG use it. Added
to progressive_config.json business_flags as ALWAYS_TRUE_CLEANUP (needs_cleanup=true).
Semantics: always TRUE → rules requiring it FALSE are dead. Finalized PLNumberOfUnits:
- `b4f59197` (empty, LOB!=Condo, flag TRUE) → System (cleaning)
- `54d2717d` (=1, Condo, hidden, flag TRUE) → Business (Condo hidden default)
- `e5b05ed3` (Agent, flag FALSE) → DEAD (archived)
- `709dec0b` (Consumer, flag FALSE) → DEAD (archived)
Also: PLNumberOfUnits is CONDO ONLY — HQX Direct error flagged to product.
Numeric batch also produced product items: NumOfDwelling (title "How many dwellings are
owned by the insured?", missing both Directs), MonthsAtAddress (ASI mapping relies on it),
BundelingAutoPolicyNum (11111 text, consumer-only business if relevant), PLNumberOfUnitsInFirewall.
PLFloorNumber → Business (hidden unless PLHighRiseCondo=Yes).

### 2026-07-07 (Progressive identity flags — config correction)
User flagged that Progressive has THREE main identity features: `Progressive_Interview`
(most common), `NoReplacementCost`, and `TriageQuestions`. If ANY is true, the rule
applies to Progressive (usually only one used per rule). **Config bug found & fixed:**
`NoReplacementCost` was wrongly classified SKIP/always-off in business_flags (because
not in LaunchDarkly), and `Progressive_Interview` sat in skip_flags. Created a dedicated
`progressive_identity_flags` section documenting the OR semantics across all three;
removed the wrong entries from business_flags/skip_flags.
**Impact check:** searched all 1694 raw .m files — NONE of the three identity flags drive
gating here (NoReplacementCost: 0 files, TriageQuestions: 0 files, Progressive_Interview:
3). This HQ2 dataset gates Progressive via Claim/source flags (InterviewFlowType 724,
ba_LightApi 96, ba_odysseyapi 22). User confirmed this HQ2 zip IS the complete Progressive
defaults set. So NO rules were wrongly dropped — no re-parse needed. Fix future-proofs
the config for other exports that may use these flags.

### 2026-07-07 (dead/ignored rules testing archive)
Built `PGR_Dead_Ignored_Rules.csv` as a regression-testing archive of everything we
drop, so old ODM info stays available after the infra transition. Modified a COPY of
the parser (`odm_defaults_archive.py`) to capture the 618 previously-just-counted
skipped rules with their skip reason, then categorized into buckets and merged with
the 16 review-decided dead/ignored rules → 634 total. Biggest buckets: file-level skip
(295), DF Consumer HQX 1.0 retired (262), FL carrier flag (24), Condo Redesign other-
tenant (19), Agent 1.0 (11). Each row: UUID + full source `.m` path + reason.

### 2026-07-07 (PL_NumberOfFloors — fully resolved, was parked)
9 rules resolved: only ONE live default kept.
- `514acb33eb3c` (Consumer, HQX 2.0/LightApi_True, hidden unless PLHighRiseCondo=Yes) → **Business**.
- cleaning pair `a8887cf2`=`6a900dce` (empty, LOB!=Condo, hidden) → **System**, collapse to one.
- DEAD/ignored (5): `...297a49e4` (needs ba_floor-questions-segment FALSE, but flag always ON),
  `...f4b1288434b0` (Consumer 1.0), `...7375c935e4c8` (Agent 1.0), self-ref A/B pair
  `...b3a0b095215b` + `...bad634524551`.
- `BPPComputerEquip` default (`64c45e2a`) → **product** (unknown field, likely not Progressive-relevant).
- **NEW FLAG:** `ba_floor-questions-segment` = ALWAYS TRUE / cleanup — added to progressive_config.json
  (business_flags). Rules requiring it false are dead.


### 2026-07-07 (checkbox batch + control-type re-verification)
**Context:** auto-triage initially classified 41 fields as "System (checkbox)" from ODM
data alone. User caught that control type must come from the Direct PAA/HQ2 columns.
Re-verified all 41 → 16 were NOT plain checkboxes. Key decisions:
1. **25 confirmed true checkboxes → System** (PAA=Checkboxes verified).
2. **PL_AdditionalStructures_Deck/Pool/HotTub/Trampoline** — consumer checkbox → System;
   agent side is Segmented Controls.
3. **PL_HeatedByOil** — consumer checkbox → System for MOST states; BUSINESS for
   specific states where the question is hidden; agent Segmented.
4. **BusinessOrDaycare** (child of BusinessOnResidencePremises; agent Dropdown):
   - 3f0fea93 (DayCare=true) → Business
   - 244590e0 (parent false) → Business
   - a1b752a3 (business, not DayCare → false) → Business + product (verify field need)
   - 8592a909 (parent false & child true → false) → System (parent-child cleaning)
5. **NonSmoker** → Business (consumer hidden default). Present in PAA/agent (Segmented),
   MISSING from HQX/consumer Direct → product to verify/add.
6. **PrimaryHome** → Business (agent hidden default). Present in HQX/consumer (Segmented),
   MISSING from PAA/agent Direct → product to verify/add.
7. **GatedOrLimited, ResHeldTrust** → product. ODM default is Consumer+hidden+false, but
   both are present in PAA/agent (Segmented) and MISSING from HQX/consumer Direct.
8. **ElectricCircuitBreaker** → product — Direct data mistake (should be Segmented both flows).
9. **AnimalsOnThePremises_None, PLHaveAnyLosses** → product (field purpose unclear).
All System/Business calls recorded in `PGR_Defaults_Classified.csv` (the emerging final
output). All product items in `PGR_Product_Review_MASTER.csv` (now 29 items).

### Decided defaults — quick reference (System/Business calls)
Fields with a FINAL classification. "Sent to product" items are NOT here — they
live only in `PGR_Product_Review_MASTER.csv`. Details for each are in the dated
entries below.

| Field | Rules | Final call | Note |
|---|---|---|---|
| PLDfForm | 92 | **Business** (DB/lookup) | Kept all — genuine state matrix, not duplication |
| RoofUpdatedYear | 36→18 | **Business** (DB) | Collapse Triage duplicate (user-decided); keep one set of 18 |

(IsMailAddress, DateOccupied, NumberOfChildernsUnder18 → product master, not listed here.)

### 2026-07-07 (ODM-ONLY resolved-canonical — IsMailAddress)
1. **IsMailAddress → ALL 12 rules to product review** (not split). Field = "is mailing
   address same as property address?". Consumer: Owners page, checkbox. Agent:
   ThreeQuickQuestions (interview start), segmented control. Two default styles:
   (a) unanswered + no mailing entered → false (checkbox/segmented default, would be
   System); (b) address-comparison inference (10 rules) comparing property vs mailing
   fields → true/false, with property-address fallback where a mailing field is unknown.
   User chose to send ALL versions to product to be certain about the comparison logic
   rather than split System/Business. In `PGR_Product_Review_MASTER.csv` (category:
   Default Logic Review). NOT the Triage pattern — two genuinely different pages.

### 2026-07-07 (ODM-ONLY resolved-canonical — RoofUpdatedYear)
1. **RoofUpdatedYear → Business (DB); COLLAPSE duplication, keep ONE set of 18.**
   36 rules = 18 unique rules duplicated 1:1 across two ODM tables (Exterior/Consumer
   + Triage/Both, both named RoofUpdateRange-dt). Verified every rule identical across
   tables. **KEY INSIGHT (user):** Triage is an AGENT-ONLY stage, so the two-table
   split is the normal ODM footprint of a field shown in both flows — not something to
   escalate. RE models stage separately, so only one rule set is needed. Dropped the
   Triage duplicate. Removed from product master (it's decided, not a question).
   Logic: roof-year estimate from PL_RoofUpdateYearRange age-band + PLYearBuilt.
   → generalized into the "Recurring Patterns" section at top of this file.

### 2026-07-07 (ODM-ONLY resolved-canonical — PLDfForm)
1. **PLDfForm → Business (DB/lookup table).** 92 rules = 92 distinct state+occupancy+
   premium-band mappings selecting DF form (DP1_Basic 25 / DP3_Special 42 / HO10 24).
   Verified: 0 exact duplicates, 0 condition→value conflicts. NOT duplication — the
   shared long condition prefix (DF feature gate) hid genuinely different state/occupancy
   tails. Keep all 92. Belongs in a lookup table keyed on state+occupancy+band, with the
   shared gate as a table precondition. Recorded in the Decisions Log (in this file).
2. **Method note:** always diff FULL conditions before declaring duplication. First-90-char
   comparison falsely suggested 42 DP3 rules were identical; they were all distinct.

### 2026-07-07 (ODM-ONLY blank-canonical session)
1. **Categorization approach:** handle blank-canonical (unresolved-to-AppData) ODM
   rows manually, per-field, without changing the resolver (user preference).
2. **Categories 1-4 confirmed** (address-sync / cleaning / checkbox-none / drop stage-only).
3. **Progressive_Preferences1 / Progressive_Preferences2 → UI-only, EXCLUDE** from defaults.
4. **OtherProductType → IGNORE** (removed in Direct).
5. **6 fields → product review** (in `PGR_Product_Review_MASTER.csv`):
   - ConstBrickVeneerPct — ODM default (51) but no Direct reference; ConstBrickPct vs ConstMasonryVeneerPct.
   - PLSwimmingPoolType — why both this and PL_PoolType? consolidate?
   - CustomFields/AddressChanged — internal field?
   - HowManyTimesInOneCalendarYear — which AppData field?
   - NumberOfChildren — target field + correct default (also in value-disagreements).
   - SwimmingPoolSafety — which AppData field?
6. **Address sub-fields** (`MailingAddress/City` etc.) confirmed as resolver limitation
   (nested address objects exist in AppData), NOT gaps. Kept as address-sync defaults.

### 2026-07-07 (AppData anchor session)
1. **RE ApplicationData is the canonical name authority.** Parsed 348 PL-Home properties
   (+118 enums) from the AppData V1 solution. Scope: PL/Homeowners + PL/Common + All_Lobs
   shared. Ignored all CL, PersonalAuto, RV, ClassicCar, Motorcycle, carrier-specific.
2. **Merge rebuilt (v2).** Original merge used single-column (Canonical) join → false gaps.
   Rebuilt with 4-column join (Canonical/GetQuote_DD/Pre-fill/Platform) → AppData canonical.
   `PGR_Defaults_Merged_v2.csv` supersedes `PGR_Defaults_Merged.csv`.
3. **Join bug found:** step-3 merge hadn't reused the classifier's multi-column join. 13 of
   15 "DIRECT-ONLY gaps" resolved once GetQuote_DD was included (5 of them ONLY via GQ_DD).
   The manual mappings the user gave were already in the GQ_DD column.
4. **AppData name mappings confirmed** (`PGR_AppData_Name_Mappings.json`, 16 mapped):
   RoofUpdated→PLRoofUpdated, NumberOfUnits→PLNumberOfUnits, IsTheHomeSkirted→HomeSkirted,
   F470ModularHome→ModularHome, PriorCarrierHomeowners→CurrentPersonalHomeownerCarrier,
   NumberOfFamilies→PL_NumOfFamilies, ReplacementCost→PersonalLineReplacementCost,
   DwellingOccupancy→OccupancyType (via GQ_DD), Bankruptcy→ForeclosureOrRepossessionOrBankruptcy.
5. **ActualCashValue ≠ ReplacementCost** — distinct fields; ActualCashValue is MFH-only.
6. **Bankruptcy** — AppData field is in the intentionally-removed (non-relevant) list, but
   Direct has a default → classified as **Business default → DB** (user decision).
7. **PreDateOccupied1 / PreEffectiveDate1** — absent from AppData AND relevancy. NOT opening
   relevancy bugs now. Include in defaults output ONLY because they have defaults (they do:
   1 and 2 rows). Carried with no AppData mapping, flagged not-yet-in-AppData.
8. **New rule established:** Direct field missing from BOTH AppData and ProgressiveCommonRelevancy
   → open a bug under the Relevancy Migration task.
9. **7 genuine DIRECT-ONLY defaults** confirmed (business defaults ODM never encoded):
   GatedOrLimited, ResHeldTrust, NonSmoker, BuiltOnSlope (all =No), PLAllPerilsDeductible=1k,
   PLPersonalLiability=300k, PersonalLineReplacementCost=ActualCashValue (Consumer).

### 2026-07-07 (defaults workflow session)
1. **Direct defaults extracted & triaged.** 92 rows with a Default Value → 2 control-type-noise
   (dropped), 45 real (into merge), 45 prose-logic (held in `..._ProseLogic_HOLD.csv`).
2. **Prose-logic fields corroborate earlier findings:** HeatingUpdate, PlumbingUpdated,
   ElectricalUpdated, PurchaseDate, DateOccupied, YearsAtAddress, ActualCashValue all carry
   conditional/computed defaults in Direct too — confirming they're not simple defaults.
3. **Merge join = Canonical+Flow; ODM rows kept expanded; both values side-by-side.**
4. **5 enum↔label equivalences confirmed** (NOT mismatches) → `PGR_Enum_Label_Normalization.json`:
   CeilingHeight (EightftOrLess=8 ft. or less), PropertyInsuranceCancelled (false=No),
   InsuranceFraud (false=No), HomeTiedDown (true=Yes), DwellingMedicalPayments (cov5000=$5k).
5. **5 fields → product review** (in `PGR_Product_Review_MASTER.csv`):
   - PurchasePrice — flow-dependent (ODM=ReplacementCost both flows; Direct=ActualCashValue Consumer)
   - NumberOfMortgagees — base 0 agrees; ODM extra rule =1 for MFH+LightApi
   - NumberOfChildren — real base disagreement (ODM 0 vs Direct 1)
   - NumberCarSpace — word vs digit + tied to field-duplication issue
   - PL_Houseoccup — corrupt FaultClamisNum3Y rule (UUID c810cd58) + valid =1 rule

### 2026-07-06 (control-type-conflict session)
- PLFloorNumber → Business (hidden unless PLHighRiseCondo=Yes).
- PurchaseDate (9), DateOccupied (16), EffectiveDate (3) → product review; verified genuine in raw ODM.
- EffectiveDate duplicate pair (c550f683 / f190b015) + Agent display-lock (586fe6d8) → product.
- PreDateOccupied1 (c1ae1302) is a SEPARATE field, not DateOccupied.
- Parser confirmed faithful to raw ODM DefaultValue attributes.

### Prior sessions
- 21 field-mapping decisions in `PGR_Field_Mapping_Decisions.csv` (loaded every run).
- Multi-column join; Multi[] fields = checkbox children; rule order (hidden→Business first, etc).
- Field duplication pairs found (NumberCarSpace / PL_NumberCarSpace etc).

---

## Open Issues
Summary table below; full detail in `OPEN_ISSUES.md` (regenerated 2026-07-12, kept in sync).

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | EffectiveDate duplicate rule pair | Medium | Product |
| 2 | EffectiveDate Agent display-lock | Medium | Product |
| 3 | All date-field defaults sign-off | Medium | Product |
| 4 | PL_NumberOfFloors 2 corrupt defaults | High | ✅ RESOLVED 2026-07-07 (re-confirmed 07-12). BPPComputerEquip→product; self-ref/1.0/floor-flag rules dead; flag cleanup in config |
| 5 | PreDateOccupied1 mis-grouped | Low | Noted |
| 6 | Chat decisions not persisted to pipeline | High (infra) | TBD |
| 7 | ODM-ONLY rows unverified | Medium | ✅ COMPLETE 2026-07-12. All 519 ODM-only (Default-type) accounted for: dead + prior-classified + address-sync + heavy-hitters + the final ~23-field tail. Step 3d done |
| 8 | Field duplication pairs (NumberCarSpace etc) | Medium | Product |
| 9 | 5 default value disagreements | Medium | Product |
| 10 | 20 DIRECT-ONLY gaps unverified | Medium | TBD (step 3c) |
| 11 | Classifier skill needs 4 updates | Medium | Awaiting user approval |
| 16 | Direct-only / prose-logic defaults | High | 🟢 9 held HOLD fields resolved 2026-07-12; any remaining prose-logic beyond those still to sweep |

---

## Files (authoritative handoff set)

**As of 2026-07-12 the handoff set is FOUR files that travel together.** The working/
intermediate CSVs below were pruned from the handoff (regenerable from the parser +
project Excel); if you still have them locally, keep them, but the four files here are
the source of truth.

### The authoritative files
- `PROJECT_PROGRESS.md` — this file. Status + Decisions Log = source of truth.
- `OPEN_ISSUES.md` — detailed open/resolved issues log (mirrors the summary table here).
- `PGR_ODM_Only_Field_Decisions.csv` — **the decision log** (Field, Rule Detail,
  Classification, Product Flag, Source, Notes). Field-level reasoning: *why* each field
  was classified as it was.
- `PGR_Product_Review_MASTER.csv` — **the only** product-review output (58 items). Append
  new items here; never create separate product CSVs.

> `PGR_Defaults_Classified.csv` is **RETIRED** (2026-07-12). It was only a simplified mirror
> of the decision log and risked drift. Do not maintain it. Per-rule detail (UUID + full
> condition + default value + classification) belongs in the FINAL file, not a second log.

### FINAL output (still to build — see FINAL OUTPUT SPEC near top)
- `PGR_Defaults_FINAL.csv` — **ONE ROW PER RULE, keyed by UUID**, with full condition,
  default value, Classification, Classification Source, OperationSource, Source File.
  This is where per-rule UUID + condition live. Build after the step-3d tail (the ~23
  unclassified fields) is done.

### Testing archive
- `PGR_Dead_Ignored_Rules.csv` — archive of all dead/skipped/ignored rules. 634 rules
  (618 parser-skipped + 16 review-decisions). Columns: Category (reason bucket), Skip
  Detail, Source File, ArchiveSource, Full Condition, etc. For regression testing during
  infra transition. Grows over time. NOTE: the raw parser capture `PGR_Skipped_Rules_RAW.csv`
  lives in the working dir only — its content is fully merged into this archive.

### Parser aux
- `PGR_Defaults_Review_Later.csv`, `PGR_Defaults_Active_Flags.csv`, `PGR_Defaults_Retired_Flags.csv`

### Docs
- `PROJECT_PROGRESS.md` (this file), `OPEN_ISSUES.md`, `README.md`

### NOT in this session (locate/regenerate)
- `PGR_Review_Defaults.csv` (last saved classifier run — 158 System/45 Business/368 Review)
- `PGR_Field_Mapping_Decisions.csv` (needed on every classifier run)
- `Field_Duplication_Issues.csv` (prior session)

---

## Pending skill update (Issue #11) — awaiting user approval

`odm-defaults-classify` skill needs 4 fixes surfaced this session:
- (a) normalize control-type synonyms before comparing (stop false CONTROL-TYPE-CONFLICT)
- (b) recognize/tag computed date defaults (FORMAT STRING, cross-field)
- (c) detect Disabled=true display-locks and route out of defaults
- (d) exact/word-boundary field matching (PreDateOccupied1 was folded into DateOccupied)

Also consider: apply `PGR_Enum_Label_Normalization.json` in the merge/compare step.

---

## 📚 REFERENCE (durable — absorbed from the former HANDOFF_SUMMARY.md)

**This is now the ONLY project doc.** HANDOFF_SUMMARY.md was merged here and deleted.

### Progressive config knowledge (progressive_config.json)
- Identity flags (any true = applies to Progressive): `Progressive_Interview`, `NoReplacementCost`,
  `TriageQuestions`. (This HQ2 dataset gates via Claim/source flags instead.)
- Source flags: `ba_LightApi` = HQX 2.0 (consumer); `ba_odysseyapi` = PAA 2.0 (agent).
- Cleanup flags (always-ON → fixate true, drop the flag): `ba_floor-questions-segment`, `ba_no-of-units`.
- `ba_fl-carriertrue` = always OFF (so "ENABLED=false" is satisfied → rule LIVE).
- `ba_df-consumer-hqx10` = retired (removed from LD) → treat as always FALSE: rules requiring it
  TRUE are dead; requiring it FALSE fire (InsideCityLimits, InsuranceFraud, PropertyInsuranceCancelled).
- Retired fields: `TriagePriorCarrierHomeowners`, `HomeNewPurchase` (+ rule: unknown=true → keep, known/value → dead).

### Extra pattern: corrupt / parse-artifact defaults
Default value == a field named in the SAME condition (e.g. BPPComputerEquip, FaultClamisNum3Y,
NunMajorViolationsLast3Years) = parse-artifact signature → product / exclude, verify raw .m.

### Working style (user preferences)
- Batch by pattern; propose classifications; user approves/corrects per batch.
- NEVER auto-decide duplication or Triage-stage collapse — surface to user.
- Verify claims against the data before recording — don't assume, don't re-derive what's already decided.
- The product sheet is the COMPLETE field set — don't invent "new" fields unless a fresh parse surfaces them.
- When the USER makes a call not confirmed by product, tag it in the decision log
  `Source: implementation-eng (pending product confirm)`.
- CSV/MD only while working; regenerate xlsx (QA views) only on request. QA CSV dropped for now.
- Do NOT edit the classifier skill without explicit approval (Issue #11).

### Parser
Skill `odm-parser`; run needs `odm_core.py` + `odm_defaults.py`, `--config progressive_config.json
--input odm_input/ --output`. Source .m files come from the HQ2_Interview zip.
**Rerun recommended before locking FINAL:** (a) prove the product sheet is complete via one diff,
(b) refresh stale UUIDs (fields moved between tables get new UUIDs — e.g. ApplicantYearofBirth),
(c) pick up condition changes. After rerun: reconcile fresh rules against the decision log + product
sheet BY FIELD NAME; renamed/moved fields lose their name-keyed decision and resurface as
"unclassified" (expected, not a new field).

---

## How to resume next session
1. Upload this file + `PGR_Defaults_Merged_v2.csv` (+ `PGR_Direct_Defaults.csv`, ODM zip if re-parsing).
2. Look at the Defaults Workflow table — pick up at the first ⚪ TBD step (currently 3c).
3. Say e.g. "continue defaults workflow — review the DIRECT-ONLY gaps" (step 3c)
   or "tackle the ODM-ONLY duplication" (step 3d).
4. Record every decision in the Decisions Log before ending.
