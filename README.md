# ODM-to-RE Migration — Project README

## What this project is

Migrating Progressive's insurance rules from IBM ODM to Bolt's Rule Engine (RE / RoBolt, C#).
Tenant: **Progressive**. Repo: `C:\Users\@username\source\repos\markets`

This README is the permanent source of truth for the migration approach,
skill structure, and pipeline. Future sessions and team members should be
able to orient from this file alone.

---

## Skill structure

```
robolt-skills/
  odm-core/
    SKILL.md              ← describes shared library, not a trigger skill
    odm_core.py           ← shared: file reading, flag extraction, condition extraction,
                             LOB extraction, dead rule detection, config I/O

  odm-defaults/
    SKILL.md              ← trigger: "parse defaults", "run odm-defaults"
    odm_defaults.py       ← imports odm_core; extracts InterviewAttributeType rules
                             outputs: Defaults.csv + Review_Later + Stage_Rules_Review
                                    + Active_Flags + Retired_Flags + Unresolved_Flags

  odm-validations/
    SKILL.md              ← trigger: "parse validations", "run odm-validations"
    odm_validations.py    ← imports odm_core; extracts validationResponse.addError rules
                             outputs: Validations.csv + Review_Later
                                    + Active_Flags + Retired_Flags + Unresolved_Flags

  odm-instructions/
    SKILL.md              ← PLANNED stub only — not yet built
    (no script yet)       ← will parse submissionService.createSubmissionMapping rules
                             for future carrier onboarding projects

  direct-reader/
    SKILL.md              ← trigger: "read directs", "sync the direct"
    direct_reader.py      ← extracts field inventory from PAA/HQX Excel files
```

---

## Migration pipeline

```
Stage 1 — Parse defaults
  ODM .m files  →  odm-defaults  →  Defaults.csv
  Milestone: Defaults.csv confirmed clean, 0 unresolved flags

Stage 2 — Classify defaults
  Defaults.csv  →  odm-defaults-classify  →  System_Defaults.csv
                                          →  Business_Defaults.csv
  Milestone: two CSVs confirmed, classification rules documented
  (Classification rules to be provided by user — skill not yet built)

Stage 3 — Generate RE code for defaults
  System_Defaults.csv  →  re-defaults-codegen  →  C# DefaultRuleCollection classes
  Tool: Claude Code (writes directly into repo)
  Milestone: classes in repo, passing review

Stage 4 — Parse validations (parallel, independent)
  ODM .m files  →  odm-validations  →  Validations.csv
  Milestone: Validations.csv confirmed clean, 0 unresolved flags

Stage 5 — Generate RE code for validations
  Validations.csv  →  re-validations-codegen  →  C# ValidationRuleCollection classes
  Tool: Claude Code
  Milestone: classes in repo, passing review

Stage 6 — Gap analysis
  Defaults.csv + Validations.csv + Direct Master CSV  →  gap-analysis  →  Gap Report
  Milestone: all gaps identified, prioritized, assigned

Stage 7 — Source of truth update
  All confirmed CSVs + C# classes  →  updated Direct files + documentation
  Milestone: new source of truth ready for next carrier
```

---

## Team split

| Person | Skill | Input | Output | Dependency |
|---|---|---|---|---|
| You | `odm-defaults` | Defaults zip | `Defaults.csv` | None |
| Coworker | `odm-validations` | Validations zip | `Validations.csv` | None — independent |
| Both | `progressive_config.json` | Shared config | — | Classify unknown flags together |

Both skills run from the same config file. If defaults run first and resolves
all unknown flags, coworker's run will start clean. If he encounters a new flag
not in the defaults zip, he classifies it and updates the shared config.

---

## Project files — load on demand

| File | When to read it |
|---|---|
| `README.md` | Orientation — you are here |
| `odm-defaults/SKILL.md` | When parsing defaults |
| `odm-defaults/odm_defaults.py` | Run directly — do not rewrite |
| `odm-validations/SKILL.md` | When parsing validations |
| `odm-validations/odm_validations.py` | Run directly — do not rewrite |
| `odm-core/SKILL.md` | When debugging shared extraction issues |
| `odm-core/odm_core.py` | Run directly — do not rewrite |
| `progressive_config.json` | Loaded by both parser scripts |
| `direct-reader/SKILL.md` | When reading Direct Interview Excel files |
| `direct-reader/direct_reader.py` | Run directly — do not rewrite |
| `PAA_2_0_Direct_Interview.xlsx` | Read via direct_reader.py only |
| `HQX2_0_Direct_Interview.xlsx` | Read via direct_reader.py only |

---

## GitHub repo — file inventory

Files currently in the repo and their status:

| File | Status | Notes |
|---|---|---|
| `README.md` | ✅ Current | This file |
| `odm_core.py` | ✅ Current | Shared extraction library — must be present for both parsers to run |
| `odm_defaults.py` | ✅ Current | Defaults parser — replaces `odm_parser.py` |
| `odm_validations.py` | ✅ Current | Validations parser — new, for coworker |
| `odm-core_SKILL.md` | ✅ Current | Reference doc for shared library |
| `odm-defaults_SKILL.md` | ✅ Current | Trigger skill for defaults parsing |
| `odm-validations_SKILL.md` | ✅ Current | Trigger skill for validations parsing |
| `odm-instructions_SKILL.md` | ✅ Current | Planned stub — not yet built |
| `progressive_config.json` | ✅ Current | Shared flag/LOB config for both parsers |
| `odm_parser.py` | ❌ Delete | Replaced by `odm_defaults.py` + `odm_validations.py` + `odm_core.py` |
| `odm-parser-SKILL.md` | ❌ Delete | Replaced by the three separate SKILL.md files above |
| `odm-parser.skill` | ❌ Delete | Old format — replaced by the three separate SKILL.md files above |

---

## Session startup

| What you want to do | Say this |
|---|---|
| Parse ODM defaults | "Parse defaults" + upload zip |
| Parse ODM validations | "Parse validations" + upload zip |
| Read Direct files | "Read directs" |
| Gap analysis | "Run gap analysis" |
| Generate C# defaults | "Generate RE code for defaults" (Claude Code) |
| Generate C# validations | "Generate RE code for validations" (Claude Code) |
| Ask about the project | Just ask — context is in this README |

---

## Why skills are split this way

**odm-defaults vs odm-validations** — different team members, different
input zips, different output columns, different C# target classes. Keeping
them separate means a change to how validation errors are extracted cannot
accidentally break defaults parsing, and vice versa. This was the direct
lesson from a previous regression where a fix to one feature broke another.

**odm-core** — the shared logic (flag parsing, dead rule detection, condition
extraction) lives in one place. A fix here benefits both skills simultaneously.
The V2 fixes (dead rule logical evaluator, flow direction awareness) live here.

**odm-instructions** — carrier submission mapping is a fundamentally different
file structure from interview rules. It has no InterviewAttributeType or
validationResponse calls. Built separately when needed for carrier onboarding.
Not part of the Progressive migration.

**re-codegen skills (planned, Claude Code)** — code generation writes directly
into the repo. Claude Code is the right tool for this — it has direct filesystem
access and doesn't require copy-pasting from artifacts. Kept separate from parsing
so the CSV review milestone is a hard gate before any code is written.

---

## Source of truth principle

Each completed stage produces documentation that stands alone. A future engineer
(or future Claude session) reading the SKILL.md files should be able to understand:
- What this stage produces and why
- How to interpret every output column
- What decisions were made and why
- What feeds in and what comes out
- Known edge cases and how they're handled

The goal is that when this migration is done, the skill files + CSVs + C# classes
together constitute a complete, auditable record of every rule decision made.

---

## Current blockers

### ⏳ Pending product approval — 3 fields with no LOB checkmarks (Direct reader)

| Field | Page | Flow | Question |
|---|---|---|---|
| `RoofUpdated` | Exterior | Agent | Which LOBs apply? |
| `RoofUpdatedYear` | Exterior | Agent | Which LOBs apply? |
| `UnderConstructionCheckList` | Exterior | Agent | Which LOBs apply? |

### 🔲 Skills not yet built

| Skill | Blocked on |
|---|---|
| `odm-defaults-classify` | User to provide system vs business classification rules |
| `re-defaults-codegen` | Clean `System_Defaults.csv` + Claude Code setup |
| `re-validations-codegen` | Clean `Validations.csv` + Claude Code setup |
| `gap-analysis` | Clean Defaults.csv + Validations.csv + Direct Master CSV |
| `odm-instructions` | Carrier onboarding project (not Progressive migration) |

---

## Key conventions

- **Canonical field name** = strip `PL_F###_` prefix from Field ID; fallback to GetQuote Data Dictionary
- **LOBs:** HO3 = Homeowners, HO6 = Condo, HO4 = Renters, MFH = Manufactured Home, DF = Dwelling Fire
- **Flows:** Agent = PAA file, Consumer = HQX file, Both = appears in both
- **Flag logic, output columns, calculated defaults** → `odm-defaults/SKILL.md`
- **Validation error extraction** → `odm-validations/SKILL.md`
- **LOB split logic, known field resolutions** → `direct-reader/SKILL.md`
- **Shared extraction bugs** → fix in `odm-core/odm_core.py` only
