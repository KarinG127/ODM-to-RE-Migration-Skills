# Progressive ODM→RE Migration — Open Issues Log

**Last updated:** 2026-07-06

All unresolved issues, blockers, and pending decisions. Each has an ID, owner,
and status so nothing is lost between sessions. Close issues by moving them to
the Resolved section at the bottom with the resolution noted.

---

## Open

### Issue #1 — EffectiveDate duplicate rule pair
**Severity:** Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
Two rules produce identical `then` blocks, differing only in their gate:
- `c550f683-0399-4241-aab3-8e432bd54cbc` (Owners 193) — gate: `Claim:InterviewFlowType_Consumer=true`
- `f190b015-b9d2-4d61-9cf9-4168af1abe81` (Owners 191) — gate: `LOB contains PersonalHome OR Condominium`

Both require `ba_LightApi_True=true`, `PreEffectiveDate1=true`, `YearsAtAddress=0`,
`PurchaseDate+1day is after TODAY`. Since `ba_LightApi` = HQX 2.0 = Consumer, the
two gates overlap and fire together.
**Decision needed:** Consolidate to one RE rule? Which gate is intended?
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #2 — EffectiveDate Agent display-lock: is it a default?
**Severity:** Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
Rule `586fe6d8-c33a-4e9c-86de-5bfbb1c793ab` (Owners 178) sets
`DefaultValue = EffectiveDate` (self) + `Disabled = true` on retrieved agent quotes
(`Claim:NewQuote_True=false`). This is a display-lock (re-show existing value, greyed
out), not a value default.
**Decision needed:** Confirm this belongs with relevancy/disabled handling, not the
defaults migration.
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #3 — All date-field defaults need product sign-off
**Severity:** Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
PurchaseDate (9), DateOccupied (16), EffectiveDate (3) all pulled from
auto-classification and routed to product. Defaults are computed expressions
(e.g. from PLYearBuilt, YearsAtAddress, PurchaseDate). Verified faithful to raw ODM.
**Decision needed:** Confirm each computed default is intended; identify any further
duplicate flow-gate vs LOB-gate pairs (likely present in DateOccupied's repeated values).
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #4 — PL_NumberOfFloors corrupt default values
**Severity:** HIGH · **Owner:** Engineering · **Status:** NEEDS INVESTIGATION
Of 7 rules, 2 have suspicious defaults:
- default = `PL_NumberOfFloors` (field defaulting to itself — parse artifact or real?)
- default = `BPPComputerEquip` (an unrelated field name as the default value)

The other 5 rows have clean default = `1`.
**Decision needed:** Inspect the 2 raw `.m` files. If corrupt, exclude; if real
cross-field logic, classify. Field stays in Review until resolved.
**Next action:** Pull the raw ODM for these 2 UUIDs and inspect the `then` block.

### Issue #5 — PreDateOccupied1 mis-grouped with DateOccupied
**Severity:** Low · **Owner:** Engineering · **Status:** NOTED
UUID `c1ae1302-62d1-4043-89d9-05d575534c1d` is field `PreDateOccupied1` (empty-string
cleaning rule), NOT `DateOccupied`. It was folded in by a substring match during review.
**Action:** Classify separately (empty + likely cleaning → probably System, but verify
Visible flag). Do not lump with DateOccupied.

### Issue #6 — Chat decisions not persisted to the pipeline
**Severity:** HIGH (infrastructure) · **Owner:** Engineering · **Status:** TBD
Decisions made verbally in chat (e.g. PLFloorNumber→Business) are not written back
into the classifier or a decisions CSV, so re-running the classifier reverts them to
"Review." This is the root cause of session-to-session confusion.
**Options:**
- (a) A `PGR_Classification_Decisions.csv` (field/UUID → final bucket + reason),
  loaded and applied by the classifier like `Field_Mapping_Decisions.csv` already is.
- (b) Manually maintain System/Business/Review CSVs with each session's edits.
**Recommendation:** Option (a) — mirrors the existing mapping-decisions mechanism.

### Issue #7 — 203 ODM-ONLY fields unverified for scope
**Severity:** Medium · **Owner:** Engineering/Product · **Status:** TBD
203 rows have an ODM default but no Direct match. Many are likely address sub-fields
(`PropertyAddress/City`) and internal fields, not real gaps — but each needs a scope
check. This is the largest Review category.
**Action:** Triage into (in-scope internal / out-of-scope / genuine gap) in a later pass.

### Issue #8 — Field duplication pairs (prior session)
**Severity:** Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
Fields existing twice under different names, e.g. `NumberCarSpace` + `PL_NumberCarSpace`,
`HowManyTimesInOneCalendarYear` + `PL_HowManyTimesInOneCalendarYear`. Non-PL holds a word
value (`"Two"`), PL_ holds typed input (`2`).
**Decision needed:** Consolidate to one field.
**Tracked in:** `Field_Duplication_Issues.csv` (from prior session — re-locate/regenerate).

### Issue #9 — Five default value disagreements (ODM vs Direct)
**Severity:** Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
Surfaced in the step-3 merge. Tracked in `PGR_Product_Review_MASTER.csv`:
- **PurchasePrice** — ODM defaults to ReplacementCost for both flows; Direct uses
  ActualCashValue for Consumer, ReplacementCost for Agent. Flow-dependent conflict.
- **NumberOfMortgagees** — base 0 agrees; ODM has one extra rule =1 for MFH+LightApi.
- **NumberOfChildren** — real base disagreement: ODM 0 vs Direct 1.
- **NumberCarSpace** — word-values (One/Two/Three) vs digit 1; tied to Issue #8.
- **PL_Houseoccup** — corrupt cross-field rule (default=FaultClamisNum3Y, UUID
  c810cd58) + a valid =1 rule. Whole field to product per user decision.

### Issue #10 — 20 DIRECT-ONLY gaps unverified
**Severity:** Medium · **Owner:** Engineering · **Status:** TBD (workflow step 3c)
20 Direct defaults (15 distinct fields) had no matching ODM rule in the merge.
Some may be genuine gaps (Direct business rules ODM never encoded); others may be
FALSE gaps from name mismatches (like the NumberCarSpace/PL_NumberCarSpace pairs).
**Action:** Review each; separate genuine gaps from naming artifacts before step 4.

### Issue #11 — Classifier skill needs 4 updates
**Severity:** Medium · **Owner:** Engineering · **Status:** AWAITING USER APPROVAL
`odm-defaults-classify` skill gaps surfaced this session:
- (a) Normalize control-type synonyms before comparing (`numeric` vs `Input field
  (Numeric)`) — stops false CONTROL-TYPE-CONFLICT flags.
- (b) Recognize/tag computed date defaults (`FORMAT STRING(...)`, cross-field).
- (c) Detect `Disabled=true` display-locks and route out of the defaults classification.
- (d) Use exact/word-boundary field matching — `PreDateOccupied1` was folded into
  `DateOccupied` by a substring match.
- Also: apply `PGR_Enum_Label_Normalization.json` in the merge/compare step.
- **(e) NEW — capture skipped rules with reasons.** The archive parser
  (`odm_defaults_archive.py`) was patched to record the 618 skipped rules instead of
  just counting them → `PGR_Skipped_Rules_RAW.csv`. Fold this capture behavior into
  the main odm-defaults skill so every run produces the dead/skipped archive.
- **(f) NEW — enhance `should_skip_file`** to report the SPECIFIC flag/reason for the
  295 "file-level skip" rules (currently coarse — they lack field-level detail because
  the file is skipped before extraction). Would let those 295 be bucketed like the rest.
**Do not edit the skill until user confirms which fixes to apply.**

### Issue #12 — Name alignment: Direct vs RE canonical (product verify)
**Severity:** Low-Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
Tracked in `PGR_Product_Review_MASTER.csv`:
- IsTheHomeSkirted / F470ModularHome — Direct names differ from RE canonical
  (HomeSkirted, ModularHome). Mapped, but confirm Direct should align to canonical.
- PL_NumOfFamilies — AppData uses `Num` while convention elsewhere is `Number`.
  Two naming versions; standardize.

### Issue #13 — ODM typo propagated into RE ApplicationData
**Severity:** Medium · **Owner:** Product/Eng · **Status:** PENDING PRODUCT REVIEW
`PLElectircalUpdated` (misspelled "Electircal") exists in the RE AppData itself,
matching the known ODM typo. Direct uses correct spelling. Part of the existing
spelling-issue tracking — now confirmed the typo is in RE, not just ODM.
**Action:** Align spelling across Direct / ODM / RE.

### Issue #14 — PreDateOccupied1 / PreEffectiveDate1 not in AppData
**Severity:** Low · **Owner:** Eng · **Status:** DEFERRED (per user)
Both absent from AppData and ProgressiveCommonRelevancy. Not opening relevancy
bugs now. They carry defaults so they appear in the defaults output, flagged as
not-yet-in-AppData. Revisit during relevancy migration.

---

### Issue #15 — Verify ba_no-of-units flag behavior (PLNumberOfUnits)
**Severity:** Medium · **Owner:** User/Eng · **Status:** RESOLVED 2026-07-07 — flag is always-ON in LD, added to config as ALWAYS_TRUE_CLEANUP
User believes `ba_no-of-units` is HQX 1.0 but ON in all environments (like
ba_floor-questions-segment). Needs to confirm what the flag actually does. IMPACT on
PLNumberOfUnits default rules IF always-ON:
- `b4f59197` (empty, LOB!=Condo, requires flag TRUE) → LIVE cleaning → System
- `54d2717d` (=1, Condo, hidden, requires flag TRUE) → LIVE → Business (already recorded)
- `e5b05ed3` (=1, Agent, requires flag FALSE) → DEAD
- `709dec0b` (=1, Consumer, requires flag FALSE) → DEAD
Once confirmed, finalize these 4 rules + add flag to progressive_config.json.
12 raw .m files reference this flag — broader than just PLNumberOfUnits.

### Issue #16 — Direct-only / prose-logic defaults not yet reviewed
**Severity:** HIGH · **Owner:** Eng · **Status:** OPEN — needed for complete final output
Step-3d review was ODM-centric. Fields can have a DEAD ODM rule but a LIVE Direct-only
default (proved by YearsAtAddress: ODM rule dead via retired TriagePriorCarrierHomeowners,
but HQX Direct has "hide + default 0 on new purchase"). The 45 prose-logic Direct defaults
set aside in `PGR_Direct_Defaults_ProseLogic_HOLD.csv` (step 2) still need classification,
plus the 45 'real' Direct defaults should be cross-checked against what ODM covered.
**Action before final output:** work through PGR_Direct_Defaults_ProseLogic_HOLD.csv and
the DIRECT-ONLY defaults; classify each (mostly Business). Some overlap fields already
reviewed from the ODM side.

## Resolved

### Issue #10 — 20 DIRECT-ONLY gaps (RESOLVED 2026-07-07)
All 20 were naming/reference artifacts, not missing defaults. Anchoring on RE
ApplicationData + using the 4-column join (Canonical/GetQuote_DD/Pre-fill/Platform)
resolved 13 immediately; the rest were hand-mapped (now in `PGR_AppData_Name_Mappings.json`).
Net: 0 true unresolved gaps. 7 genuine Direct-only business defaults remain (expected,
tracked in the merge v2). See Decisions Log 2026-07-07 AppData session.

### Value-mismatch triage (2026-07-07)
The 14 step-3 value-mismatches were fully triaged: 5 confirmed as enum↔label
encoding equivalences (→ `PGR_Enum_Label_Normalization.json`, no longer mismatches),
5 routed to product (Issue #9), and the remaining rows were re-examined and folded
into those two groups. No mismatch left unclassified.
