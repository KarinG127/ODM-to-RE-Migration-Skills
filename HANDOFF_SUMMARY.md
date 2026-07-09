# HANDOFF SUMMARY — Progressive ODM→RE Defaults Migration
_Created to continue in a fresh conversation. Upload this + the files listed at the bottom._

---

## WHAT THIS PROJECT IS
Migrating Progressive's IBM ODM interview rules to Bolt's new Rule Engine (RE).
This is **Stage 1 of 4 = DEFAULTS** (later stages: Validation/Kickouts, Relevancy, Stages — NOT started).
Every default rule must be classified:
- **System** → goes into RE code
- **Business** → goes into DB (AdminDefault)
- **Product-Review** → needs product input (in the product master file)
- **Dead** → retired/never-fires (archived for regression testing)

Classification is **PER-RULE, not per-field**: one field can have rules in System, Business AND Dead.

**Deadline: user needs the final output very soon (was "tomorrow").**

---

## WHERE WE ARE (as of this handoff)

### The 8-step defaults workflow
```
1-3. Extract ODM + Direct + Merge + gaps         ✅ DONE
3d.  ODM-ONLY review:
     ├─ blank-canonical (40 fields)              ✅ DONE
     └─ resolved-canonical:
          ├─ heavy-hitters (5)                   ✅ DONE
          ├─ checkbox batch (41 fields)          ✅ DONE
          ├─ numeric batch (6)                   ✅ DONE
          └─ REVIEW fields (39)                  ✅ DONE
Direct-only defaults check (Issue #16)           🟡 IN PROGRESS (16 cross-checked, 9 new pending)
2-3 rule + single-rule ODM fields                ⚪ NOT STARTED
4.   Build PGR_Defaults_FINAL.csv                 ⚪ NOT STARTED (spec below)
```

### Current tallies
- `PGR_Defaults_Classified.csv` — 83 rows of System/Business decisions (working log)
- `PGR_Product_Review_MASTER.csv` — 54 product items
- `PGR_Dead_Ignored_Rules.csv` — 646 archived dead/skipped rules
- Universe = **571 live DEFAULT rules** (933 total minus 362 relevancy)

---

## IMMEDIATE NEXT STEPS (in order)
1. **FINISH Direct-only defaults check (Issue #16, HIGH).** We were mid-way.
   - The 16 already-classified prose-logic fields were CROSS-CHECKED — this caught a real
     miss: **ElectircalUpdated, ElectircalUpdatedYear, HeatingUpdateYear, PlumbingUpdatedYear**
     had Business computed defaults we'd under-recorded (only had the System cleaning half).
     NOW CORRECTED in Classified.
   - **STILL PENDING: 9 genuinely-new prose-logic Direct fields, user wants each reviewed individually:**
     `1283_DogsBreedsSelection` (state→NoneOfTheAbove), `Bankruptcy` (Agent, True if
     FinancialHardships=Bankruptcy), `DateOccupied` (15th of purchase month — already in product),
     `DwellingOccupancy` (if hidden→Owner-Primary; = OccupancyType, likely covered),
     `ElectricalUpdated` (correctly-spelled TWIN of typo'd ElectircalUpdated — dedupe issue),
     `LivingTime` (Consumer, 9-12 months if PrimaryHome), `PurchaseDate` (date — already in product),
     `ReplacementCost` (Agent, blank if not data-filled), `RoofResponsible` (Agent, True if Condo).
   - Source file: `PGR_Direct_Defaults_ProseLogic_HOLD.csv` (45 rows / 25 fields).
2. **2-3 rule + remaining single-rule ODM fields** (auto-triaged, unconfirmed).
3. **Build `PGR_Defaults_FINAL.csv`** (spec below).

---

## FINAL OUTPUT SPEC (build LAST)
`PGR_Defaults_FINAL.csv` — **ONE ROW PER RULE**, keyed by UUID. Columns:
- UUID, Field, AppData Canonical (identity)
- Flow, LOBs, Visible, Page (scope)
- Full Condition, Default Value (the rule)
- **Classification**: System | Business | Product-Review | Dead
- **Classification Source**: confirmed-decision | auto-triage | archive
- **OperationSource** (supportsite audit): DB/Business default → "AdminDefault" (more values TBD)
- Source File (.m path)
Plus a SUMMARY sheet with counts (System / Business / Product / Dead).
NOTE: `PGR_Defaults_Classified.csv` is a WORKING LOG (field + free-text label), NOT the deliverable.

---

## CRITICAL RULES & PATTERNS LEARNED (apply to every field)

### Control type is PER-FLOW
Direct has TWO columns: `Control Type` = PAA/agent, `HQ2 Control Type` = HQX/consumer.
Same field is often checkbox (consumer) / Segmented (agent). NEVER infer control type from ODM.
Boolean value ≠ checkbox. Classification can differ by flow.

### Classification heuristics
- Checkbox (confirmed via Direct) → System. Segmented/Dropdown with default → usually review/Business.
- Hidden field default → Business. Visible simple init (stepper=0) → System.
- Empty-default cleaning rule (clear a field when parent/condition) → System (cleaning).
  Cleaning rules can live on a SIBLING field (e.g. clear PlumbingUpdatedYear when PLPlumbingUpdated=NotUpdated).
- Computed/cross-field defaults (state/LOB/age logic, =OtherField, FORMAT STRING) → Business.
- Self-referential default (field = itself, on edit/retrieved quote) → display-lock, archive/ignore.

### Duplication
- Verify on FULL conditions (shared prefixes hide real differences).
- **Triage-stage duplication**: Triage is AGENT-ONLY. A field in both a Triage table and
  another page = normal ODM footprint. If rules identical across tables, RE needs ONE set.
  **NEVER auto-collapse — ALWAYS surface to user.** (RoofUpdatedYear collapse was a user decision,
  not standing permission.)

### Dead-rule detection (flags)
- Always-ON flags → rules requiring them FALSE are dead: `ba_floor-questions-segment`, `ba_no-of-units`.
- `ba_LightApi_False IS ENABLED=true` OR `ba_LightApi_True IS ENABLED=false` = HQX 1.0 = dead.
- `ba_odysseyapi_True IS ENABLED=false` = Agent 1.0 = dead.
- `ba_fl-carriertrue` = always OFF, so "IS ENABLED=false" is satisfied → rule LIVE.

### Retired fields in conditions
- `RetiredField is unknown` → always TRUE → KEEP rule (treat clause as true).
- `RetiredField is known` / value-check → dead rule.
- Retired: `TriagePriorCarrierHomeowners`, `HomeNewPurchase` (both also need Direct correction → product).

### Other recurring product-flag patterns
- Orphaned cleaning logic (clears a field for an option the platform no longer has, e.g. "Other",
  "Apartment") → product, not System.
- Parent / child-Multi[] / Type triplets (BurglarAlarm/BurglarAlarmTypeMulti[]/BurglarAlarmType):
  Direct maps to the Multi[] variant → plain Type field orphaned → product.
- Agent-only fields not marked as such in PAA Direct → product (needs a consistent indicator).
- Carrier Questions / RC1: PAA Carrier Questions sheet has per-carrier columns (v/LOB) +
  "Value for RC1 submission" col = the business default for agent carrier-question fields.
- Missing-from-Direct: always state WHICH Direct — format `PAA/agent: ... | HQX/consumer: ...`.

### OperationSource (final output audit field)
DB/Business default → "AdminDefault".

---

## PROGRESSIVE CONFIG KNOWLEDGE (all in progressive_config.json)

### Progressive identity flags (ANY true = rule applies to Progressive)
`Progressive_Interview` (most common), `NoReplacementCost`, `TriageQuestions`.
The latter two are NOT in LaunchDarkly but ARE valid — don't treat as dead.
(None appear in this HQ2 dataset — it gates via Claim/source flags instead. Confirmed complete.)

### Source flags
`ba_LightApi` = HQX 2.0 (consumer). `ba_odysseyapi` = PAA 2.0 (agent).

### Flags added/confirmed this session
- `ba_floor-questions-segment` → ALWAYS_TRUE_CLEANUP (on in all envs, should be cleaned).
- `ba_no-of-units` → ALWAYS_TRUE_CLEANUP (HQX 1.0, on in LD, Homesite+AMIG use it; needs impl as true/false).
- `ba_fl-carriertrue` → always OFF.
- `ba_utilities-replaced-question` → already in config, gates 42 utilities-update rules.

### Retired fields (in config → retired_fields)
`TriagePriorCarrierHomeowners`, `HomeNewPurchase` + a `_RULE` note (unknown=true, known/value=dead).

---

## FILE CONVENTIONS (IMPORTANT)
- **ONE product-review file only**: `PGR_Product_Review_MASTER.csv`. APPEND new items with a
  `Category` value — NEVER create separate product CSVs.
- Every product row carries a source reference: **ODM Reference (UUID)** for ODM-sourced,
  **Direct Reference** (Field ID + sheet, or PAA/HQX presence) for Direct-sourced.
- Decided System/Business calls → the Decisions Log in PROJECT_PROGRESS.md (+ Classified CSV).
- Dead/ignored rules → PGR_Dead_Ignored_Rules.csv (full detail: UUID, condition, source .m path).
- `progressive_config.json` in outputs is the UPDATED working copy — user must save it back to the
  project (read-only original is at /mnt/project/).

---

## WORKING STYLE (user preferences)
- Batch fields by pattern; propose classifications; user approves/corrects per batch.
- NEVER auto-decide duplication/Triage collapse — surface to user.
- Verify claims against data before recording (don't assume). User supplies tenant knowledge
  (flags, retired fields, RC1, carrier questions, control types) that must be captured in config/patterns.
- Document frequently; keep PROJECT_PROGRESS.md Decisions Log + recurring patterns current.
- Use present_files after updates.
- Parser: skill at odm-parser; run needs odm_core.py + odm_defaults.py, --config progressive_config.json
  --input odm_input/ --output. The 1694 .m files come from HQ2_Interview zip.

---

## OPEN ISSUES (see OPEN_ISSUES.md for detail)
- **#16 (HIGH, OPEN)**: Direct-only/prose-logic defaults — IN PROGRESS (9 new fields pending).
- **#11**: Classifier skill needs updates incl. (e) fold skip-capture into skill, (f) enhance
  should_skip_file to report specific flag for the 295 coarse "file-level skip" rules.
- **#6**: Chat decisions not auto-persisted — PROJECT_PROGRESS.md is the authoritative record.
- Others: value disagreements, date fields, name-alignment, RE typo PLElectircalUpdated, etc.
