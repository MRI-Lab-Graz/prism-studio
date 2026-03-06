# Mypy + Repo Check Roadmap (2026-03-06)

## Goal
Bring repository checks to stable, non-mutating behavior and drive runtime type checking (`mypy`) to zero actionable errors for maintained code.

## What Is Done

### 1. Repo-check hardening (completed)
- `tests/verify_repo.py` now avoids repo side effects during checks.
- Added `PYTHONDONTWRITEBYTECODE=1` to command execution paths to prevent `.pyc` churn.
- `entrypoints-smoke` now restores/deletes `app/prism_studio_settings.json` after smoke run to keep checks non-mutating.
- Replaced interactive `safety check` flow with non-interactive `python -m pip check` in dependency check.

### 2. Vendor exclusion policy (completed)
- Added `vendor` exclusion in:
  - `tests/verify_repo.py` Black/Flake8/Ruff paths.
  - `pyproject.toml` Black exclude list.
- `mypy` check in `tests/verify_repo.py` now scopes to maintained runtime code trees: `app/src` and `src`.

### 3. Typing remediation progress (in progress, strong reduction)
- Baseline at start of remediation pass: 177 errors in 39 files (runtime scope).
- Current snapshot (`prism-studio_report_2026-03-06_18-02-46.txt`):
  - **49 errors in 21 files** (checked 143 source files).
- Net reduction in this pass: **-128 errors**, **-18 files**.

### 4. Files already improved in this pass
- `app/src/web/blueprints/conversion_participants_helpers.py`
- `app/src/web/blueprints/conversion_participants_blueprint.py`
- `app/src/web/blueprints/conversion.py`
- `app/src/web/blueprints/conversion_biometrics_handlers.py`
- `app/src/web/blueprints/conversion_survey_handlers.py`
- `app/src/web/blueprints/conversion_physio_handlers.py`
- `app/src/web/blueprints/tools.py`
- `app/src/web/blueprints/validation.py`
- `app/src/converters/csv.py`
- `app/src/converters/excel_to_survey.py`
- `src/converters/limesurvey.py`
- `app/prism-studio.py`
- `tests/verify_repo.py`
- `pyproject.toml`
- `app/src/batch_convert.py`
- `src/batch_convert.py`
- `app/helpers/physio/convert_varioport.py`
- `app/src/utils/io.py`
- `app/src/web/blueprints/tools_recipes_surveys_handlers.py`
- `app/src/web/blueprints/tools_helpers.py`
- `app/src/web/upload.py`

## Current Hotspots (Top Remaining)
- `src/converters/anc_export.py` (9)
- `app/src/converters/survey_io.py` (7)
- `app/src/web/blueprints/projects_citation_helpers.py` (6)
- `app/src/validator.py` (4)
- `src/converters/survey.py` (3)

## Remaining Plan (Execution Order)

### Phase A: Fast structural fixes (high ROI)
- Eliminate remaining `no-redef` and optional import assignment patterns.
- Normalize fallback import signatures across blueprint/helper modules.
- Target: reduce another 20-30 errors quickly.

### Phase B: Data-shape typing fixes
- Focus files:
  - `app/src/web/blueprints/tools_helpers.py`
  - `app/src/web/blueprints/projects_citation_helpers.py`
  - `app/src/converters/survey_io.py`
- Resolve `object`/`dict` confusion with explicit typed intermediates and guards.

### Phase C: Batch conversion cores
- Focus files:
  - `app/src/batch_convert.py`
  - `src/batch_convert.py`
- Resolve mixed scalar/collection assignments, regex match typing, and `DictReader` input typing.

### Phase D: Physio typing cleanup
- Focus file: `app/helpers/physio/convert_varioport.py`
- Resolve iterable assumptions and dict value type inconsistencies.

### Phase E: Final strict pass
- Run full `verify_repo --check mypy` and ensure zero errors in scoped runtime trees.
- Re-run focused smoke/tests to guard against regressions.

## Lessions Learned
- Repo checks must be side-effect free; even `--help` commands can mutate config files if import-time writes exist.
- Excluding vendored code from format/lint/type checks prevents noisy churn and accidental third-party edits.
- Most mypy volume came from a small number of files; ranking by file count is the fastest path to progress.
- `no-redef` and optional-import patterns can be fixed safely with alias imports plus typed placeholders.
- Constraining `mypy` to maintained runtime trees (`app/src`, `src`) made cleanup tractable and policy-aligned.

## Resume Commands
```bash
source .venv/bin/activate
python tests/verify_repo.py --check mypy --no-fix

# Optional direct run for iterative fixing
mypy app/src src --ignore-missing-imports --explicit-package-bases --python-executable '.venv/bin/python' --exclude '(\.venv|venv|env|\.git|node_modules|__pycache__|\.idea|\.vscode|build|dist|eggs|\.eggs|.*_report_.*\.txt|vendor)'
```
