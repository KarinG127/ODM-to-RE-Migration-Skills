---
name: odm-instructions
description: "PLANNED — NOT YET BUILT. Will parse IBM ODM carrier instruction/submission mapping files (.m extension with submissionService.createSubmissionMapping calls). For future carrier onboarding use cases. Do not trigger this skill — it does not exist yet."
---

# ODM Instructions Parser Skill — PLANNED

## Status

⚠️ **This skill is not yet built.** This file documents what it will do
so that future sessions have the context to build it correctly.

## What this skill will do

Parse IBM ODM carrier submission mapping files — the instruction rules that
map PolicyData fields to carrier-specific XML paths for quote submission.

These are structurally different from defaults and validations:
- Package name: e.g. `Homesite.Mappings.HO3.RC1`
- `then` block calls: `submissionService.createSubmissionMapping(CarrierID, LOB, quoteData.FieldName, "/xpath/path", DIRECT, "")`
- Also calls: `relevancyService.createFieldsRelevancy(CarrierID, LOB, ["PolicyData/FieldName"], DIRECT, "")`
- Properties include: `CarrierID`, `LOB`, `Exclude`
- No `InterviewAttributeType` or `validationResponse` calls

## Example file structure (Homesite, HO3, RC1)

```
BAL:
  if
    - (Progressive_Interview IS ENABLED = true)
    AND (ba_paa-rc1-olb_True IS ENABLED = true)
    AND (State in ["AZ"])
then
  submissionService.createSubmissionMapping(
    "Homesite", "PersonalHome",
    quoteData.PLSquareFootage,
    "/root/dwellings[@id='0']/details/livingAreaSQF[@Integer='true']",
    DIRECT, ""
  );
  relevancyService.createFieldsRelevancy(
    "Homesite", "PersonalHome",
    ["PolicyData/PLSquareFootage"],
    DIRECT, ""
  );
```

## Key extractions needed

| Output column | Source |
|---|---|
| `Carrier` | `CarrierID` property |
| `LOB` | `LOB` property |
| `Field Name` | `quoteData.FieldName` arg in createSubmissionMapping |
| `Carrier XPath` | XPath string arg in createSubmissionMapping |
| `Strategy` | `DIRECT` / other strategy type |
| `Relevancy Fields` | Field array in createFieldsRelevancy |
| `Conditions` | ORIGINAL_BAL conditions (state, A/B test flags, etc.) |
| `Flow` | From Claim flags (same as defaults/validations) |

## Shared with odm-core

File reading, skip detection, flag extraction, condition extraction, LOB extraction —
all from `odm_core.py`. Only the `then` block parsing and output building are new.

## When to build this skill

When starting a carrier onboarding project that involves migrating ODM carrier
instruction files. Not needed for the Progressive migration (that project
uses defaults and validations only).

## Files to create when building

```
robolt-skills/
  odm-instructions/
    SKILL.md              ← update this stub with full documentation
    odm_instructions.py   ← new script importing odm_core
```

## Notes from sample files (Homesite HO3 RC1 zip)

- 13 files in the sample, all same carrier/LOB/conditions
- Conditions include A/B test flags (`ABTest-boltolb-hsi`) and state filters
- Each file maps one field — same pattern as defaults (one field per file)
- `Exclude` property exists — may need to handle `Exclude = true` as a skip
- Both SUBMISSION and RELEVANCY action types appear in the same file's then block
