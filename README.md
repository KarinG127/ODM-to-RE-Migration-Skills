# ODM-to-RE Migration — Project README

## What this project is

Migrating Progressive's insurance rules from IBM ODM to Bolt's Rule Engine (RE / RoBolt, C#).
Tenant: **Progressive**. Repo: `C:\Users\karing\source\repos\markets`

---

## Project files — load on demand, not upfront

| File | When to read it |
|---|---|
| `README.md` | Orientation only — you are here |
| `odm-parser-SKILL.md` | When doing any ODM parsing work |
| `odm_parser.py` | When actually running the parser (copy to container, don't rewrite) |
| `progressive_config.json` | When parsing — contains all flag/LOB/routing knowledge |
| `direct_reader_SKILL.md` | When reading the Direct Interview Excel files |
| `direct_reader.py` | When actually running the direct reader (copy to container, don't rewrite) |
| `PAA_2_0_Direct_Interview.xlsx` | Read via direct_reader.py only — Agent flow field definitions |
| `HQX2_0_Direct_Interview.xlsx` | Read via direct_reader.py only — Consumer flow field definitions |

**Do not read scripts or xlsx files directly unless the task requires them.**

---

## Session startup — say one of these to begin

| What you want to do | Say this |
|---|---|
| Parse ODM rules | "Parse this" + upload zip |
| Read Direct files | "Read directs" |
| Gap analysis | "Run gap analysis" |
| Generate C# rules | "Generate RE code for [Defaults / Relevancy / Validations]" |
| New tenant | "Parse this — new tenant called [Name]" |
| Ask about the project | Just ask — context is in this README |

Claude will read only the files needed for your session type.

---

## File index & current status

| File | Status | Notes |
|---|---|---|
| `odm-parser-SKILL.md` | ✅ Complete | Full parser workflow, flag logic, new tenant guide |
| `odm_parser.py` | ✅ Active | Generic parser — never rewrite, only run |
| `progressive_config.json` | ✅ Active | All Progressive flag/LOB classifications |
| `direct_reader_SKILL.md` | ✅ Complete | Full reader workflow, LOB split logic, known field resolutions |
| `direct_reader.py` | ✅ Active | Direct reader — never rewrite, only run |
| `PAA_2_0_Direct_Interview.xlsx` | ✅ Active | Read via direct_reader.py |
| `HQX2_0_Direct_Interview.xlsx` | ✅ Active | Read via direct_reader.py |

**Skills still to build:** `gap-analysis`, `re-codegen`

---

## Migration phases

| Phase | Description | Skill | Status |
|---|---|---|---|
| 1 | Extract canonical field inventory from Direct files | `direct-reader` | ✅ Built — 515 fields extracted, 3 fields pending product approval (see below) |
| 2 | Parse ODM rules → structured CSVs (Defaults, Relevancy, Validations) | `odm-parser` | ✅ Built — last run: 1,074 rules parsed, 0 unresolved flags |
| 3 | Join Direct + ODM → gap analysis master document | `gap-analysis` | 🔲 Not built — blocked on Phase 1 completion |
| 4 | Master document → C# RE rule classes | `re-codegen` | 🔲 Not built |

---

## Current blockers

### ⏳ Pending product approval — 3 fields with no LOB checkmarks in Direct Excel

These fields appear in `Progressive_Direct_Warnings.csv` on every run until resolved.
Once LOBs are confirmed, update the Excel source or add a post-processing override in `direct_reader.py`.

| Field | Page | Flow | Question |
|---|---|---|---|
| `RoofUpdated` | Exterior | Agent | Which LOBs apply? |
| `RoofUpdatedYear` | Exterior | Agent | Which LOBs apply? |
| `UnderConstructionCheckList` | Exterior | Agent | Which LOBs apply? |

---

## Key conventions (quick ref)

- **Canonical field name** = strip `PL_F###_` prefix from Field ID; fallback to GetQuote Data Dictionary
- **LOBs:** HO3 = Homeowners, HO6 = Condo, HO4 = Renters, MFH = Manufactured Home, DF = Dwelling Fire
- **Flows:** Agent = PAA file, Consumer = HQX file, Both = appears in both
- **Flag logic, output columns, C# patterns, calculated defaults** → all documented in `odm-parser-SKILL.md`
- **LOB split logic, known field resolutions** → documented in `direct_reader_SKILL.md`

---

## After a session where config or skills changed

Download the updated file and replace it in Project attachments:
- Config changed → replace `progressive_config.json`
- Skill updated → replace the relevant `*-SKILL.md`
- Script updated → replace the relevant `.py` file
