---
name: direct-reader
description: "Use this skill whenever you need to extract field inventory from Progressive's Direct Interview Excel files (PAA_2_0_Direct_Interview.xlsx and HQX2_0_Direct_Interview.xlsx) into a structured master CSV. Triggers when the user says 'read directs', 'extract fields from the Direct files', 'build master CSV', 'run direct-reader', or asks to update/sync the master field inventory. Also triggers when a Direct file has been updated and the master CSV needs refreshing. This skill produces the Layer 1 base inventory that all downstream skills (gap-analysis, re-codegen) depend on."
---

# Direct Reader Skill

Extracts the Progressive field inventory from both Direct Interview Excel files
into a unified master CSV. This is Layer 1 of the migration pipeline —
pure extraction, no derivation, no ODM data. Everything downstream depends on this output.

---

## Files

| File | Flow | Sheets to skip |
|---|---|---|
| `PAA_2_0_Direct_Interview.xlsx` | Agent | DI Guide, Change Control |
| `HQX2_0_Direct_Interview.xlsx` | Consumer | Version Control |

Both files are in `/mnt/project/`. Copy to `/home/claude/` before reading.

---

## How to Run

```bash
cp /mnt/project/PAA_2_0_Direct_Interview.xlsx /home/claude/
cp /mnt/project/HQX2_0_Direct_Interview.xlsx /home/claude/
pip install openpyxl pandas --break-system-packages -q
python3 /home/claude/direct_reader.py
```

Trigger phrase: **"read directs"**

Output: `/home/claude/Progressive_Direct_Master.csv`

Copy to outputs when done:
```bash
cp /home/claude/Progressive_Direct_Master.csv /mnt/user-data/outputs/
cp /home/claude/Progressive_Direct_Warnings.csv /mnt/user-data/outputs/
```

---

## Sheet Handling

| Sheet type | How to identify | Action |
|---|---|---|
| Guide/control sheets | DI Guide, Change Control, Version Control | Skip entirely |
| Standard data sheets | Row 1 = column headers including "Field ID" | Extract normally |
| Carrier Questions (PAA) | Has carrier columns: HSI, Hippo, Bamboo, PGRH, etc. | Extract with `Carrier` scope — see below |

### Page Name Normalization
Always normalize sheet tab names on output: trim whitespace, collapse double spaces.
e.g. `Assumptive -  (Details)` → `Assumptive - (Details)`
This prevents join mismatches in downstream gap-analysis when matching on Page.

---

## Column Mapping

The script maps raw Excel columns to standardized output columns.
Column names vary slightly between sheets (e.g. "HO3 " vs "HO3") — use `.strip()` on all headers.

### Standard sheets

| Output Column | Source Column(s) | Notes |
|---|---|---|
| `Field ID` | `Field ID` | e.g. `PL_F472_TypeOfFoundation` |
| `Canonical Name` | `Field ID` → strip `PL_F###_` prefix; fallback to `GetQuote Data Dictionary` | e.g. `TypeOfFoundation` |
| `Pre-fill Element` | `Pre-fill Element` | e.g. `PolicyData.TypeOfFoundation` |
| `Page` | Sheet tab name | e.g. `Exterior` |
| `Flow` | Source file | PAA = `Agent`; HQX = `Consumer` |
| `LOBs` | `HO3`, `DF`, `MFH`, `Condo` columns | Collect headers where cell = `v`; map Condo → HO6 |
| `Label` | `Label` or ` Label` (leading space variant) | Strip whitespace |
| `Control Type` | `Control Type` or ` Control Type` | Strip whitespace |
| `Value List` | `Value List` | Raw enum values |
| `Field Format` | `Field Format` | Numeric / Date / Text / N/A |
| `Default Value` | `Default value` or `Consumer Default Value` | Raw — no interpretation |
| `Display Rules` | `Display Rules` | Raw condition text |
| `Mandatory` | `Mandatory - If Question Displays` | Yes / No |
| `BOLT Error Message` | `BOLT Error Message` | Validation error text |
| `Kickout` | `Kickout` | Hard stop condition (PAA only) |
| `Parent or Child` | `Parent or Child Question` | Parent / Child / blank |
| `Prefill Values` | `Prefill values` | Vendor prefill values |
| `Presented if Prefilled` | `Presented if vendor Prefilled` | v / blank |
| `Presented if Not Prefilled` | `Presented if vendor Not Prefilled` | v / blank |
| `Carrier` | — | Empty for standard sheets; populated for Carrier Questions sheet |
| `Source File` | Filename | `PAA` or `HQX` |

### Carrier Questions sheet (PAA only)

Same mapping as above except:
- `LOBs` → from `HO3`, `DF`, `MFH`, `Condo` columns if present
- `Carrier` → collect carrier column headers where cell = `v` (HSI, Hippo, Bamboo, PGRH, Foremost, AMod, NTW, NatGen, Assurant, Openly, P Rock, American Integrity, Stillwater, Tower Hill)

---

## Row Handling Rules

### Strikethrough rows

Strikethrough formatting means the field was removed or edited. The rule
depends on **which cell** is struck — not whether the whole row is struck:

| Condition | Action |
|---|---|
| Field ID cell is struck | Skip the entire row — field is deleted |
| Any other cell(s) struck but Field ID is clean | Keep the row, add `Strikethrough Note` column with: which cell was struck and its original value |
| No strikethrough | Normal row |

**How to detect strikethrough in openpyxl:**
```python
def cell_is_struck(cell) -> bool:
    return bool(cell.font and cell.font.strike)

def row_strike_status(row_cells: list, header_map: dict) -> tuple:
    """
    Returns (skip: bool, note: str)
    skip=True  → Field ID cell is struck, skip entire row
    skip=False → keep row; note describes any struck non-Field-ID cells
    """
    field_id_col = header_map.get('Field ID')
    notes = []
    for cell in row_cells:
        if not cell_is_struck(cell):
            continue
        if cell.column == field_id_col:
            return True, ''
        # Non-Field-ID cell struck — note it
        col_name = next((k for k, v in header_map.items() if v == cell.column), str(cell.column))
        val = str(cell.value)[:60] if cell.value else '(empty)'
        notes.append(f'{col_name}: "{val}"')
    return False, '; '.join(notes) if notes else ''
```

Add a `Strikethrough Note` column to the master CSV output. Empty = no strikethrough.
Non-empty = which cells were struck and what they contained.

Do not add a `Status` column for now — Active/Strikethrough/Deleted tracking is
part of the future Notion design. For now, the Strikethrough Note column is sufficient.

### Skip these rows
- Field ID starts with `Section:` or `Disclaimer:` — UI dividers, not real fields
- GetQuote DD column starts with `Section:` or equals `Selected Carrier`, `Prefill Verification`, `Carrier Questions` — PAA Overview pattern where section labels land in the wrong column
- Field ID is `N/A` or empty AND label is a UI text block (e.g. "We have everything we need...")
- Field ID is empty AND no label

### Split these rows
- Field ID cell contains multiple IDs separated by `\n`
  e.g. `PL_F10_FirstName\nPL_F11_MiddleName\nPL_F12_LastName\nPL_F38_DOB`
- Split into one row per Field ID, deduplicating by Field ID
- Each split row gets its own Canonical Name
- LOBs are re-derived per split field using the original Excel row (see LOB split logic below)

### Keep as-is
- Everything else with a valid Field ID

---

## Canonical Name Derivation

```python
import re

def canonical_name(field_id, getquote_dd):
    if field_id and field_id != 'N/A':
        match = re.match(r'^PL_F\d+_(.+)$', str(field_id).strip())
        if match:
            return match.group(1)
        match = re.match(r'^PL_(.+)$', str(field_id).strip())
        if match:
            return match.group(1)
        return str(field_id).strip()
    if getquote_dd and str(getquote_dd).strip() not in ('N/A', ''):
        return str(getquote_dd).strip()
    return ''
```

---

## LOB Mapping

| Direct column | Master CSV value |
|---|---|
| `HO3` | `HO3` |
| `DF` | `DF` |
| `MFH` | `MFH` |
| `Condo` | `HO6` |

Collect all LOB columns where cell value = `v` (case-insensitive, strip whitespace).
Output as comma-separated string e.g. `HO3, HO6, MFH`.
If all four present → `All`.
If none → flag as `LOB_MISSING` — do NOT leave blank. Write to `Progressive_Direct_Warnings.csv`.

### LOB Split Logic (multi-field rows)

When a row is split, LOBs must be re-derived per field from the **original Excel row**, not the normalized `norm` dict. Two patterns exist in the Excel:

**Pattern A — Single `v` covers all fields in the group:**
```
Field ID:  PL_F10_FirstName\nPL_F11_MiddleName\nPL_F12_LastName
HO3 cell:  v         ← one v applies to all three fields
```
→ All split fields get the same LOBs.

**Pattern B — One `v` per field (newline-separated):**
```
Field ID:  PL_F1278_Farm1to2\nPL_F129_Farm3orMore\nPL_F1280_Exotic
HO3 cell:  v\nv\nv   ← one v per field
```
→ Each split field gets its own LOB value by index.

Implementation: `get_lobs(raw_row, header_map, field_index=i)` where:
- If `len(parts) == 1` → single v, apply to all fields
- If `len(parts) > 1` → pick `parts[field_index]`

Always pass the original `row_dict` (keyed by original Excel column names) into `get_lobs`, not the `norm` dict (which uses mapped column names and loses the LOB columns).

---

## Known LOB_MISSING Fields — Unresolved

These fields have no LOB checkmarks in the Excel and are pending confirmation. They appear in `Progressive_Direct_Warnings.csv` on every run until resolved.

| Field | Page | Flow | Status |
|---|---|---|---|
| `RoofUpdated` | Exterior | Agent | ⏳ Awaiting team clarification |
| `RoofUpdatedYear` | Exterior | Agent | ⏳ Awaiting team clarification |
| `UnderConstructionCheckList` | Exterior | Agent | ⏳ Awaiting team clarification |

Once confirmed, add the correct LOBs to the Excel source or handle via a post-processing override in the script.

## Known LOB_MISSING Fields — Resolved

These were previously LOB_MISSING and are now confirmed:

| Field | Page | LOBs | Notes |
|---|---|---|---|
| `MailAddressLine1/2`, `MailingZipCode`, `MailCity`, `MailState` | Overview/Owner | All | LOB-agnostic |
| `PreviousAddressLine1/2`, `PreviousZipCode`, `PreviousCity`, `PreviousState` | Triage/Property | All | LOB-agnostic |
| `FirstName`, `MiddleName`, `LastName`, `DOB` | Owner/Overview | All | LOB-agnostic |
| `CoFirstName`, `CoMiddleName`, `CoLastName` | Owner | All | LOB-agnostic |
| `BusinessOrDaycare`, `TypeOfBusinessDD` | Owner | All | LOB-agnostic |
| `DoYouHaveLosses` | Final Details | All | LOB-agnostic |
| `AnimalsOnThePremises_Farm1to2/3orMore/Exotic` | Assumptive | All | Multi-field split row |
| `SmokeDetector`, `FireExtinguisher`, `SprinklerSystem`, `FireDetection` | Discount | All | Multi-field split row |
| `PoolFeatures_Slide`, `RemovableLockableLadder`, `PoolFeatures_ScreenEnclosure/SurroundingWall/OtherPoolBarrier` | Exterior/Assumptive | HO3, DF, MFH | Multi-field split row |
| `HotTubFeatures_ScreenEnclosure/SurroundingWall/OtherHotTubBarrier/LockableLid` | Exterior/Assumptive | HO3, DF | Multi-field split row |
| `FuelTanksBelowGround` | Carrier Questions | HO3 | Bamboo carrier only |

---

## Direct Sync (when Direct file is updated)

### Current approach — version-based full re-read

When the user uploads an updated Direct file or says "sync the direct":

1. Read the **Change Control / Version Control** sheet first (cheap — one sheet, few rows)
2. Extract the latest version number from the `Version` column (last non-empty row)
3. Compare against the version stored in `direct_version_cache.json` (written after every run)
4. If version is the same → skip, tell the user nothing changed, do not re-read
5. If version changed → full re-read of all sheets → overwrite `Progressive_Direct_Master.csv`
6. Update `direct_version_cache.json` with the new version number
7. Report: version before → after, total fields extracted, any new strikethrough fields found

**Cache file format** (`direct_version_cache.json`):
```json
{
  "paa_version": "2.1",
  "hqx_version": "1.4",
  "paa_last_read": "2025-07-05",
  "hqx_last_read": "2025-07-05"
}
```

Store this file alongside the script in the repo so both team members share the
same version baseline. Commit it after every sync run.

Trigger phrases: **"sync the direct"** / **"direct was updated"** / **"read directs"**

Note: "read directs" always checks version first. Full re-read only happens if
version changed or no cache exists yet.

### Future — incremental field-level sync (Notion)

A more token-efficient approach using Notion as the queryable store with row-level
hash comparison is planned. See README.md — Future Options section. Not built yet.
Build this when the migration is complete and the smart panel work begins.

---

## Output

| File | Contents | Written when |
|---|---|---|
| `Progressive_Direct_Master.csv` | Full field inventory — one row per field per page per flow | Always |
| `Progressive_Direct_Warnings.csv` | Fields with no LOBs, items needing investigation | Non-empty only |

After extraction, report:
- Total rows extracted
- Rows per flow (Agent / Consumer)
- Rows per page
- Any rows skipped and why
- Any multi-field rows that were split
- Any fields written to Warnings CSV

---

## Notes

- Column headers have inconsistencies across sheets — always `.strip()` all header names before matching
- Most PAA sheets have `HO3 ` (trailing space) in the header — strip handles this
- Carrier Questions sheet has many more columns than standard sheets — unknown columns are ignored
- `2.0 consumer mapping` and `Legacy mapping` columns are informational only — captured as-is
- `Version` column tracks which sprint introduced the field — essential for direct-sync, always capture
- Page names must be normalized before output — downstream skills join on Page name, double spaces break joins
- HQX blank columns are not always gaps — check for inheritance disclaimer before flagging
- Do NOT split Field IDs on `/` — `N/A` would be split into `N` and `A`. Split on `\n` only
