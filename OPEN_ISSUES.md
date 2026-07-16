# Progressive ODM→RE Migration — Open Issues Log

**Last updated:** 2026-07-15
**Relationship to PROGRESS:** `PROJECT_PROGRESS.md` is the primary source of truth and
carries a summary Open-Issues table. This file is the *detailed* issues log. Keep the two
consistent; when an issue changes, update both.

All unresolved issues, blockers, and pending decisions. Each has an ID, owner, and status
so nothing is lost between sessions. Close issues by moving them to the Resolved section at
the bottom with the resolution noted.

---

## Open

### Issue #1 — EffectiveDate duplicate rule pair
**Severity:** Medium · **Owner:** Product · **Status:** HANDLED 2026-07-15 — computed-date tagging + condition-aware merge collapse exact flow twins; distinct gates stay separate. Confirm final gate with product.
Two rules produce identical `then` blocks, differing only in their gate:
- `c550f683-0399-4241-aab3-8e432bd54cbc` (Owners 193) — gate: `Claim:InterviewFlowType_Consumer=true`
- `f190b015-b9d2-4d61-9cf9-4168af1abe81` (Owners 191) — gate: `LOB contains PersonalHome OR Condominium`

Both require `ba_LightApi_True=true`, `PreEffectiveDate1=true`, `YearsAtAddress=0`,
`PurchaseDate+1day is after TODAY`. Since `ba_LightApi` = HQX 2.0 = Consumer, the two gates
overlap and fire together.
**Decision needed:** Consolidate to one RE rule? Which gate is intended?
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #2 — EffectiveDate Agent display-lock: is it a default?
**Severity:** Medium · **Owner:** Product · **Status:** HANDLED 2026-07-15 — Disabled=true display-locks now routed OUT of defaults (DISABLED-DISPLAY-LOCK). Product to confirm relevancy handling.
Rule `586fe6d8-c33a-4e9c-86de-5bfbb1c793ab` (Owners 178) sets `DefaultValue = EffectiveDate`
(self) + `Disabled = true` on retrieved agent quotes (`Claim:NewQuote_True=false`). This is a
display-lock (re-show existing value, greyed out), not a value default.
**Decision needed:** Confirm this belongs with relevancy/disabled handling, not defaults.
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #3 — All date-field defaults need product sign-off
**Severity:** Medium · **Owner:** Product · **Status:** RESOLVED 2026-07-15 — walked with product: PurchaseDate/DateOccupied→Business (computed, ba_yearbuild-default-date=TRUE); EffectiveDate agent display-lock routed out, 2 consumer/both→Business; PL_RoofUpdateYearRange→System.
PurchaseDate (9), DateOccupied (16), EffectiveDate (3) all routed to product. Defaults are
computed expressions (e.g. from PLYearBuilt, YearsAtAddress, PurchaseDate). Verified faithful
to raw ODM.
**Decision needed:** Confirm each computed default is intended; identify any further
duplicate flow-gate vs LOB-gate pairs (likely present in DateOccupied's repeated values).
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #5 — PreDateOccupied1 mis-grouped with DateOccupied
**Severity:** Low · **Owner:** Engineering · **Status:** RESOLVED 2026-07-15 — spelling suggester guarded so PreDateOccupied1/DateOccupied & PreEffectiveDate1/EffectiveDate never merge.
UUID `c1ae1302-62d1-4043-89d9-05d575534c1d` is field `PreDateOccupied1` (empty-string cleaning
rule), NOT `DateOccupied`. It was folded in by a substring match during review.
**Action:** Classify separately (empty + likely cleaning → probably System, verify Visible).
Do not lump with DateOccupied.

### Issue #6 — Chat decisions not persisted to the pipeline
**Severity:** HIGH (infrastructure) · **Owner:** Engineering · **Status:** CLOSED / DESCOPED 2026-07-15 — decided this is a one-time migration on a stable ODM, so no rerun-persistence layer is needed. The overlay JSON was created then dropped. Decisions are written directly into `PGR_Defaults_FINAL_corrected.csv` (Classification + Classification Reason), which is the single source of truth.
Decisions made verbally in chat weren't written back, so re-running reverted them to "Review."
**Progress:** `PGR_Defaults_Decisions.json` overlay now created — 389 UUID overrides (Business 184,
System 141, Refactor 27, Investigate 21) harvested from the corrected FINAL, plus explicit #1–#5/batch
decisions keyed by UUID and Direct-only field. All manual work is now DATA, not memory.
**Remaining:** consume the overlay in the (new) consolidation script — see Issue #20. Once wired,
classifier→consolidate→overlay reproduces the FINAL end-to-end.

### Issue #8 — Field duplication pairs
**Severity:** Medium · **Owner:** Product · **Status:** RESOLVED 2026-07-15 — name aliases encoded in PGR_Defaults_Field_Mapping_Decisions.csv (8 SAME pairs); Direct wins on value; duplicates fold in coverage/merge.
Fields existing twice under different names, e.g. `NumberCarSpace` + `PL_NumberCarSpace`,
`HowManyTimesInOneCalendarYear` + `PL_HowManyTimesInOneCalendarYear`. Non-PL holds a word
value (`"Two"`), PL_ holds typed input (`2`). Also `PLSwimmingPoolType` + `PL_PoolType`
(consolidation question — see Issue #7 tail decision).
**Decision needed:** Consolidate to one field per pair.
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #9 — Default value disagreements (ODM vs Direct)
**Severity:** Medium · **Owner:** Product · **Status:** RESOLVED 2026-07-15 — reviewed via PGR_Carrier_Review.csv: RC1 'No' etc. are UI labels, ODM enum (false) wins; same-meaning cases keep ODM; Bankruptcy Direct wins. Remaining carrier value fixes are Direct-side edits product will make.
Tracked in `PGR_Product_Review_MASTER.csv`:
- **PurchasePrice** — ODM defaults to ReplacementCost both flows; Direct uses ActualCashValue
  (Consumer) / ReplacementCost (Agent). Flow-dependent conflict.
- **NumberOfMortgagees** — base 0 agrees; ODM has one extra rule =1 for MFH+LightApi.
- **NumberOfChildren** — base disagreement: ODM 0 vs Direct 1.
- **NumberOfChildernsUnder18** — ODM 0 vs Direct 1 (hidden demographic inference). RESTORED
  to product 2026-07-12 after being lost in a file deletion.
- **NumberCarSpace** — word-values (One/Two/Three) vs digit 1; tied to Issue #8.
- **PL_Houseoccup** — RESOLVED 2026-07-15: number stepper → System (consumer) + Business (agent, carrier Q);
  corrupt FaultClamisNum3Y row (c810cd58) dropped as parse artifact.
- **ReplacementCost / ActualCashValue** — RESOLVED 2026-07-15: ReplacementCost has NO default (consumer=prefill-only,
  agent=user-answers) → both rows dropped. ActualCashValue (Consumer/MFH) → Business, cross-field = ReplacementCost when known else blank.

### Issue #10 — DIRECT-ONLY gaps
**Severity:** Medium · **Owner:** Engineering · **Status:** RESOLVED (see Resolved section)

### Issue #11 — Classifier skill needs updates
**Severity:** Medium · **Owner:** Engineering · **Status:** RESOLVED 2026-07-15 — (a) control-type synonym+substring normalization; (b) computed-date tagging; (c) Disabled=true display-lock routed out; (e) enum-label normalization + Default Match; (d/f) parser skip_reason + Disabled extraction. Skill docs updated.
`odm-defaults-classify` skill gaps:
- (a) Normalize control-type synonyms before comparing (`numeric` vs `Input field (Numeric)`).
- (b) Recognize/tag computed date defaults (`FORMAT STRING(...)`, cross-field).
- (c) Detect `Disabled=true` display-locks and route out of defaults classification.
- (d) Use exact/word-boundary field matching (`PreDateOccupied1` vs `DateOccupied`).
- (e) Capture skipped rules with reasons (fold the archive-parser behavior into the main skill).
- (f) Enhance `should_skip_file` to report the specific flag/reason for file-level skips.
- Also apply `PGR_Enum_Label_Normalization.json` in the merge/compare step.
**Do not edit the skill until user confirms which fixes to apply.**

### Issue #12 — Name alignment: Direct vs RE canonical
**Severity:** Low-Medium · **Owner:** Product · **Status:** PENDING PRODUCT REVIEW
- IsTheHomeSkirted / F470ModularHome — Direct names differ from RE canonical (HomeSkirted,
  ModularHome). Mapped, but confirm Direct should align.
- PL_NumOfFamilies — AppData uses `Num` vs convention `Number`. Standardize.
- **RoofResponsible** (added 2026-07-12) — Direct `PL_RoofResponsible` vs GQ_DD `RoofResponsible`
  vs ODM `RoofResponsible`; plus a flow discrepancy (ODM consumer cleaning-only vs Direct agent
  Condo=True) that changes the LOB. Verify whether UI-only.
**Tracked in:** `PGR_Product_Review_MASTER.csv`

### Issue #13 — ODM typo propagated into RE ApplicationData
**Severity:** Medium · **Owner:** Product/Eng · **Status:** PENDING PRODUCT REVIEW
`PLElectircalUpdated` (misspelled "Electircal") exists in RE AppData, matching the ODM typo.
Direct uses correct spelling.
**Action:** Align spelling across Direct / ODM / RE.

### Issue #14 — PreDateOccupied1 / PreEffectiveDate1 not in AppData
**Severity:** Low · **Owner:** Eng · **Status:** DEFERRED (per user)
Both absent from AppData and ProgressiveCommonRelevancy. Carry defaults so they appear in the
defaults output, flagged as not-yet-in-AppData. Revisit during relevancy migration.


### Issue #17 — Refactor / Investigate fields need carrier verification (NEW 2026-07-15)
**Severity:** Medium · **Owner:** Product/Carrier-mapping · **Status:** OPEN — verification list produced. All Refactor (70) rows carry a carrier-verify note; PGR_Carrier_Review.csv lists specific items + UUIDs. Awaiting carrier→field mapping to complete.
Refactor (27, remove from PGR interview): BurglarAlarmType(+Multi), FireDetectionType(+Multi),
MitRoofCover/Wall/Deck, NumberOfChildren, HomeNewPurchase, TriagePriorCarrierHomeowners.
Investigate (21, need info): MitSecWaterResis, DealershipPurchase (Foremost MFH), SwimmingPool,
TrampolineOnPremises, PL_PoolFeatures_None, PL_AdditionalStructures_None, NumberOfChildernsUnder18
(ASI-only; Direct AGENT default unknown=1 vs ODM 0 → Direct wins; move to carrier-level ASI mapping).
**Action:** verify no PGR carrier is affected before removing; move ASI/FL-carrier fields to carrier-level mappings.

### Issue #18 — 6 genuine Direct-only defaults to confirm
**Severity:** Low-Medium · **Owner:** Product/Eng · **Status:** RESOLVED 2026-07-15
Bankruptcy → Business · DwellingOccupancy → Business · PreEffectiveDate1 → Business (deduped) ·
LivingTime → renamed PL_LivingTime, Business (hidden consumer, PrimaryHome-gated) ·
PlumbingUpdated → name-twin of ODM PLPlumbingUpdated (Coverage BOTH, alias) · ReplacementCost → dropped (no default).

### Issue #19 — ElectircalUpdatedYear
**Severity:** Low-Medium · **Owner:** Eng · **Status:** RESOLVED 2026-07-15
Not merely a typo-twin — UUID `01b5f03f` is a BUG (maps YearBuilt when systems are NOT updated; has a bug ticket) → dropped.
The other three (`74f0ecd2` hidden house-age<20, `19fe5f58` flag-off new-experience, `01b0ae98`) → Business; empty cleaning rule (`146be4a7`) → System.

### Issue #20 — FINAL build/consolidation is unscripted (NEW 2026-07-15)
**Severity:** —  · **Owner:** Engineering · **Status:** CLOSED / WON'T-DO 2026-07-15 — decided NOT to build a consolidation script: the FINAL merge is tenant-specific and better done by command per tenant. The reusable layer is the classify SKILL documentation (FINAL-build section), not a script.
`odm_defaults_classify.py` only emits separate System/Business/Review/Gaps CSVs. The merged FINAL
(Coverage, Merged UUIDs, Merged Rule Count, Refactor/Investigate buckets, flow-merge, field-overrides)
was built ad-hoc and is only *documented* in the classify skill, never scripted. Root cause of "doing things twice."
**Action:** build `odm_defaults_consolidate.py` implementing the documented merge + field-override rules +
Coverage + Refactor/Investigate, consuming `PGR_Defaults_Decisions.json`. Validate it reproduces the corrected FINAL
(minus the 46 rows that re-resolve under the updated Direct). Then classifier→consolidate→overlay is fully reproducible.

### Issue #21 — Flags surfaced this session (NEW 2026-07-15)
**Severity:** Low · **Owner:** Eng · **Status:** RESOLVED 2026-07-15 — CORRECTION: all these flags were ALREADY in progressive_config.json with correct effective values (my earlier claim that they needed adding was wrong). This session refined 3 classification labels IMPLEMENT→CLEANUP (ba_fl-carriertrue, ba_tmp_preference_redesign_cr618, ba_yearbuild-default-date) so they route to the cleanup/retired bucket. ba_Condo_Redesign was already ALWAYS_TRUE_CLEANUP. Tracker (PGR_Flags_To_Clean.csv) = 10 flags. Config is current; effective values were always correct so current output is unaffected either way.
- `ba_fl-carriertrue` → always FALSE (ENABLED=true → dead; ENABLED=false → fires). Code cleaned, ODM missed. Controls triage Qs. Backlog cleaning story. Remove from ODM.
- `ba_abtest-naming-convention` → always TRUE. Relevancy-only rules; carrier no longer PGR; code cleanup, no user story.
- `ba_tmp_preference_redesign_cr618` → always TRUE (ON all envs; TRUE in all ODM refs). Verify behavior; remove from interview JSONs. ODM-only, no user story.
All three added to `PGR_Flags_To_Clean.csv` (now 9). Config entries pending — only affect a future ODM re-parse (ODM currently untouched).

### Issue #22 — direct_reader skips 'Three Prefill Questions' sheet (NEW 2026-07-15)
**Severity:** Low · **Owner:** Eng · **Status:** OPEN (no data loss)
`direct_reader.py` skips the HQX `Three Prefill Questions` sheet, which isn't in the skill's documented skip list.
Verified the 6 fields (YearBuilt, SF, ArchitectureStyle, MHArchitectureStyle, Length, Width) all appear on other sheets → no loss.
**Action:** add the sheet to the skill's skip list explicitly (make the skip intentional), or extract if 3PQ-specific defaults ever appear.

### Issue #23 — Progressive_Preferences1/2 (NEW 2026-07-15)
**Severity:** Medium · **Owner:** Product · **Status:** OPEN — THE ONLY remaining defaults review item (11 rows, marked PENDING REVIEW in the FINAL). Needs ba_tmp_preference_redesign_cr618 behaviour + whether fields migrate. Preferences1 default NunMajorViolationsLast3Years is a parse-artifact (do not migrate as-is).
`Progressive_Preferences1` default `NunMajorViolationsLast3Years` = parse-artifact (default is a field named in its own condition) →
annotated "do NOT migrate as-is; verify raw .m". `Progressive_Preferences2` 1/2/3 = clean cross-field map from PL_ScaleKickoutQuestions.
The 10/11/12 defaults on both are gated by `ba_tmp_preference_redesign_cr618` (see #21). Whole fields kept in Product-Review.

### Issue #24 — Updated Direct shifts the Product-Review set (NEW 2026-07-15)
**Severity:** — · **Owner:** Eng/Product · **Status:** RESOLVED 2026-07-15 — Direct regenerated (PAA v22/HQX 12.9); the entire Product-Review list was walked field-by-field against the updated Direct. From 171 review items down to 11 (Preferences only).
Product updated the Direct after last session (PAA v22 / HQX 12.9). Regenerated `Progressive_Direct_Master.csv` (515 rows).
**46 of the 171** Product-Review rows were ODM-ONLY (no Direct match) but NOW match under the updated Direct
(PL_NumberOfFloors, DwellingUsage, OccupancyType, PLFloorNumber, PLTypeOfDwelling, EffectiveDate, …).
**Decision:** rerun-first (via Issue #20 consolidation) so these re-resolve, THEN do field-by-field on the result. Do not decide the 46 blind.

---


---

## Resolved

### Issue #4 — PL_NumberOfFloors corrupt default values (RESOLVED 2026-07-07, re-confirmed 07-12)
Of the 9 Default rules: 2 empty (a8887cf2 = 6a900dce) → System cleaning (collapse); 1 Business
(1d9549a6, hidden unless PLHighRiseCondo=Yes); 4 dead (Agent/Consumer 1.0 retired-flag rules +
the self-referential A/B-test pair 86bf543c/347f631f); and `64c45e2a` (default = `BPPComputerEquip`)
→ **product** as a suspected parse artifact / corrupt default. The self-reference default was an
old A/B test (user-confirmed via rule history). `ba_floor-questions-segment` confirmed always-ON
→ moved to CLEANUP; recorded in `progressive_config.json` (business_flags).

### Issue #7 — ODM-ONLY fields unverified for scope (RESOLVED 2026-07-12)
The count grew from the stale "203" to 519 ODM-only rows (all Default-type) as the parse expanded.
All accounted for: 27 dead + prior-classified + address-sync (BlankCanonical) + heavy-hitters
(PLDfForm 92 Business, RoofUpdatedYear 18 Business, IsMailAddress product) + the final ~23-field
tail (2026-07-12): 17 clear-when-not-applicable → System; PL_PoolType → System (+ product
consolidation Q); BuiltOnSlope → Business (agent carrier question, FC1 stage); InsideCityLimits →
Product (no Direct reference). **Step 3d (ODM-ONLY review) is complete.**

### Issue #15 — ba_no-of-units flag behavior / PLNumberOfUnits (RESOLVED 2026-07-07)
Flag always-ON in LD; added to config as ALWAYS_TRUE_CLEANUP. Resulting rule calls:
`b4f59197` → System (live cleaning), `54d2717d` → Business (live), `e5b05ed3` + `709dec0b` → dead.

### Issue #16 — Direct-only / prose-logic defaults (RESOLVED 2026-07-12)
The 9 held fields from `PGR_Direct_Defaults_ProseLogic_HOLD.csv` were classified:
DogsBreedsSelection → Business (state, merged) + System (cleaning); Bankruptcy → Business
(DIRECT→DB); RoofResponsible → System (consumer) + Business (agent Condo) + product (name/flow);
ReplacementCost → Drop (no default, prefill-only); LivingTime → Drop (PL_LivingTime is only a
condition feeding OccupancyType); DwellingOccupancy = OccupancyType; DateOccupied / PurchaseDate /
ElectricalUpdated confirmed already-covered. If any prose-logic Direct defaults beyond these 9
remain in the (pruned) HOLD file, re-sweep when regenerated; the 9 that were held are done.

### Issue #10 — 20 DIRECT-ONLY gaps (RESOLVED 2026-07-07)
All 20 were naming/reference artifacts, not missing defaults. Anchoring on RE ApplicationData +
the 4-column join resolved 13 immediately; the rest hand-mapped (now in
`PGR_AppData_Name_Mappings.json`). Net: 0 true unresolved gaps. 7 genuine Direct-only business
defaults remain (expected, tracked in the merge v2).

### Value-mismatch triage (RESOLVED 2026-07-07)
The 14 step-3 value-mismatches were fully triaged: 5 enum↔label encoding equivalences
(→ `PGR_Enum_Label_Normalization.json`), 5 routed to product (Issue #9), the rest folded in.
No mismatch left unclassified.

## Resolved (added 2026-07-15)

### Merge philosophy — condition-aware flow merge (RESOLVED 2026-07-15)
Earlier field+default-only merge over-collapsed distinct-condition rules (lost data). Fixed to merge ONLY
rules identical except the flow flag (same field+default+flow-agnostic condition). 26 merges, 516 individual,
sum Merged Rule Count = 568 (0 lost). Rationale: ODM worked per-stage so a default can appear twice; RE sends
all defaults at once, so exact-condition flow twins are safe to collapse. Verified with 3 examples.

### Issue #9 value disagreements — captured as VALUE-MISMATCH (RESOLVED 2026-07-15)
ODM-vs-Direct default mismatches now flagged VALUE-MISMATCH with "Direct wins". NumberOfChildernsUnder18 → Investigate.
