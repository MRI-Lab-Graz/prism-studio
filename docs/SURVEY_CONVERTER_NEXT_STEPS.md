# Survey PRISM Converter — Next Steps (Survey-only)

## Goal
Create a **PRISM survey converter** that takes a “wide” data export (Excel / SPSS / CSV) and writes a **BIDS-compatible PRISM dataset** for **survey data** by:

1. Reading a tabular file with participant rows and item columns (e.g., `ADS01`, `ADS02`, …).
2. Looking up each item column in the **Survey Library templates** (JSON) under `library/survey/`.
3. Exporting per-subject (and optionally per-session) survey TSVs plus dataset-level sidecars in a way that:
   - does **not change BIDS standards**, and
   - remains compatible with BIDS apps (PRISM is an add-on, not a replacement).

## Non-goals (for this scope)
- No imaging, audio, physio, events conversion.
- No schema changes to BIDS standards.
- No “smart” inference of questionnaires beyond exact template matches (keep deterministic).

## Inputs (what we should support)
- **CSV**: straightforward (`scripts/csv_to_prism.py` already exists and can be the starting point).
- **Excel** (`.xlsx`): common for study exports and data dictionaries.
- **SPSS** (`.sav`): common for psychology studies.

Implementation-wise, treat everything as a table (`rows = participants`, `columns = variables`).

## Template source of truth
Templates are **Golden Masters** in `library/survey/survey-*.json`.

Example (from `survey-ads.json`):
- Metadata blocks: `Technical`, `Study`, `Metadata`
- Item keys: `ADS01`, `ADS02`, …

### Template indexing (needed for fast matching)
Build an index at startup:
- `item_id -> template_name` (e.g., `ADS01 -> ads`)
- `template_name -> set(item_id)`
- `template_name -> TaskName` (from `Study.TaskName`, if present)

**Assumption**: item IDs are unique across the whole library (the library workflow already enforces uniqueness). If duplicates exist, treat as an error because mapping becomes ambiguous.

## Column/header matching rules
### 1) Normalize headers safely
We need a conservative normalization that won’t break item IDs:
- Trim whitespace
- Optionally normalize common export quirks (e.g., replace spaces with underscores)

But do **not** auto-change case for instrument items unless you have a strict mapping rule, because `ADS01` vs `ads01` should be handled explicitly.

### 2) Split columns into: participant/admin vs survey items
Typical exports mix:
- **Participant/admin**: `participant_id`, `subject`, `CODE`, `Group`, age, sex, etc.
- **Survey items**: `ADS01`, `PSS10`, etc.

Proposed approach:
- Maintain a small set of **reserved/known participant columns** (configurable):
  - required: `participant_id` (or equivalent)
  - optional: `session`/`visit`, `run`, `group`, demographics fields
- Everything else is treated as “candidate item columns” and matched against the survey library.

### 3) Match each item column to the library
For each candidate item header:
- Exact match against `item_id` keys in templates.
- If not found:
  - classify as `unknown_column` and report it.
- If found in multiple templates (shouldn’t happen):
  - classify as `ambiguous_column` and error.

### 4) Coverage report (before writing output)
Always print/write a report (dry-run friendly):
- Which templates are detected
- Which columns mapped to which template
- Unknown columns
- For each detected template: missing expected items (optional warning, because exports can be partial)

This report is critical for trust and for debugging real-world messy exports.

## Output format (BIDS-compatible PRISM)
### Survey data files
For each subject (and optionally session), write TSVs in the PRISM survey modality folder:
- `sub-<label>/[ses-<label>/]survey/sub-<label>[_ses-<label>]_task-<task>_beh.tsv`

Notes:
- Use `task-<task>` where `<task>` is the survey/instrument name (e.g., `ads`).
- Keep TSV columns = the matched item IDs for that instrument (stable ordering).

### Survey sidecars
Copy/write dataset-level sidecars for BIDS inheritance:
- `surveys/survey-<task>_beh.json`

This aligns with the current validator logic in `src/validator.py` which searches for dataset-level survey sidecars under the dataset root and `surveys/`.

## Participants handling (minimal but necessary)
Because many exports include participant information, the converter should support:
- Mapping a column to BIDS subject IDs (e.g., `participant_id` or `CODE`).
- Optionally generating:
  - `participants.tsv`
  - `participants.json` (if we want type/levels metadata)

Keep this minimal:
- Only include columns the user explicitly opts into (or a conservative whitelist).
- Do not attempt to infer complex categorical levels unless requested.

## Proposed implementation plan (milestones)
### Milestone 1 — Header scan + mapping report (no writing)
- Implement loader for CSV first.
- Load templates from `library/survey/`.
- Build item index.
- Produce a deterministic mapping report:
  - templates detected
  - per-column mapping
  - unknown/ambiguous columns

Acceptance criteria:
- Given an export with headers like `participant_id, ADS01, ADS02`, the tool reports `ads` detected and 2 items mapped.

### Milestone 2 — Write survey TSVs + sidecars (CSV)
- Reuse/extend `scripts/csv_to_prism.py` logic if possible.
- For each row, write subject TSVs into the PRISM structure.
- Copy `library/survey/survey-<name>.json` into `surveys/survey-<task>_beh.json`.

Acceptance criteria:
- Output validates with `python prism-validator.py <dataset>`.

### Milestone 3 — Excel input
- Add `.xlsx` reading.
- Confirm stable header parsing (Excel exports often include merged/blank header cells).

Acceptance criteria:
- Same mapping + output as CSV for the same data.

### Milestone 4 — SPSS input
- Add `.sav` reading.
- Ensure value labels (if present) do not replace the raw coded values unless explicitly requested.

Acceptance criteria:
- Preserves numeric codes; outputs TSV suitable for analysis.

### Milestone 5 — Sessions/runs (optional)
- If the table has repeated measurements:
  - support a `session`/`visit` column mapping to `ses-<id>`
  - support a `run` column mapping to `_run-<n>`

Acceptance criteria:
- Multiple rows per subject are routed into the correct `ses-*` folders (and/or `run-*` files).

### Milestone 6 — Web UI integration (later)
Because the web interface is based on `prism-validator.py` logic, keep conversion as a core utility that the web UI can call.

## New feature stream: Derivatives (survey scoring)
Once a PRISM dataset is already valid, we also want to generate **derivatives** for one or more surveys, e.g.:
- reverse-code (invert) specific items (e.g. `0→3`, `1→2`, …)
- compute subscores / total scores (sum or mean)

### Derivative “recipes” (rules)
Recipes live in the repo under:
- `derivatives/surveys/*.json`

Each recipe targets a survey via `Survey.TaskName` (e.g. `ads`) and defines:
- `Transforms.Invert` (optional): list of items + min/max scale
- `Scores`: list of computed columns (`sum` or `mean`)

### CLI
Compute survey derivatives for a PRISM dataset root:

```bash
python prism_tools.py derivatives surveys --prism /path/to/prism
```

Run only one survey recipe (optional):

```bash
python prism_tools.py derivatives surveys --prism /path/to/prism --survey ADS
```

Behavior:
- If `--survey` is omitted, all recipes under `derivatives/surveys/` are considered.
- A recipe is applied only if matching survey TSVs exist in the dataset (e.g. `sub-*/ses-*/survey/*_task-ads_*`).
- Outputs are written into the dataset under `derivatives/surveys/<recipe>/...`.

## CLI sketch (suggested)
A single entry point is enough:

```bash
python scripts/survey_convert.py \
  --input raw.xlsx \
  --library library/survey \
  --output /path/to/dataset \
  --id-column participant_id \
  --session-column visit \
  --dry-run
```

Recommended flags:
- `--dry-run` (report only)
- `--unknown {error,warn,ignore}`
- `--task-mode {template_taskname,filename,manual_map}`

## Open questions (need decisions)
1. Subject ID policy: do we enforce `sub-001` style numbering, or allow `sub-<original>`?
2. How strict should unknown columns be by default (error vs warning)?
3. Do we want to support multi-instrument exports where different instruments share prefixes but not templates?
4. Participants metadata: do we generate `participants.tsv` automatically or only when requested?

## Related docs
- `docs/SURVEY_DATA_IMPORT.md` (current workflow: dictionary → library → CSV import)
- `docs/SURVEY_LIBRARY.md` (draft/publish model for templates)
- `docs/LIMESURVEY_INTEGRATION.md` (survey structure conversion and naming conventions)
