# Eligibility Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criteria entered once in the project metadata are checked against `participants.tsv` by the validator, as warnings, via a link set per column in the sociodemographics panel.

**Architecture:** One new backend module `src/eligibility.py` reads `Eligibility.Criteria` from `project.json` and the `EligibilityCriterion` link from `participants.json`, and returns warning tuples. `validate_dataset` calls it. The link travels through the existing `--neurobagel-schema` passthrough. The GUI only renders criteria rows and a select.

**Tech Stack:** Python (pytest), vanilla JS modules (vitest), existing Flask blueprints.

**Spec:** `docs/superpowers/specs/2026-10-16-eligibility-validation-design.md`

## Global Constraints

- Warnings only, never errors; nothing blocks save or convert.
- Limits live only in `project.json`; `participants.json` holds only `"EligibilityCriterion": "<id>"`.
- Numeric bounds are inclusive, either may be missing; `include` flags values outside the range, `exclude` flags values inside it.
- Categorical `values` are labels, never raw codes; labels compared as exact strings.
- Logic only in top-level `src/eligibility.py`, imported as `src.eligibility`; no `app/src/` copy (CLAUDE.md dual-tree rule). Check with `python3 -c "import src.eligibility as m; print(m.__file__)"`.
- Test first for every task. Session labels and codes are never normalized.
- Issue tuples have the same shape as `_validate_citation_cff` in `app/src/runner.py` (level, message, code).

## Review Focus

- Criterion with `min` greater than `max`: one config warning, criterion skipped, no crash. (Task 1)
- Decimal comma values such as `17,5` parse like the survey range check does. (Task 1)
- `project.json` missing, invalid JSON, or without `Criteria`: no output, no crash. (Task 1)
- Link naming a criterion id that no longer exists in `project.json`: one warning. (Task 1)
- Two criteria with the same `id`: one warning, the first wins. (Task 1)
- Label compare is exact (`male` does not match `Male`); no `Levels` on a linked categorical column: one "cannot be checked" warning. (Task 4)

---

### Task 1: Numeric check and schema

**Files:**
- Create: `src/eligibility.py`
- Modify: `app/schemas/stable/project.schema.json` (add `Criteria` under `Eligibility`, shape per spec Data model)
- Test: `tests/test_eligibility.py`

**Interfaces:**
- Produces: `check_eligibility(root_dir: str) -> list[tuple[str, str, str]]`. Reads `<root>/project.json`, `<root>/participants.json`, `<root>/participants.tsv`. Warning code `PRISM602` for a participant outside a criterion, `PRISM603` for "criterion cannot be checked" (bad config, missing column, unknown id, no Levels).

- [ ] **Step 1: Write failing tests** in `tests/test_eligibility.py`, building a tmp dataset with a helper `_make(tmp_path, criteria, participants_json, rows)`:
  - `test_include_range_flags_outside_values`: age include 18-35; rows 17, 18, 35, 36 → exactly two `PRISM602` warnings (sub of 17 and 36), message contains `sub-P01`, `17` and `18-35`.
  - `test_exclude_range_flags_inside_values`: IQ exclude `max 69`; values 69, 70 → one warning.
  - `test_open_ended_bounds`: include `min 85` only.
  - `test_empty_na_and_non_numeric_skipped`: `""`, `n/a`, `abc` → no warnings.
  - `test_decimal_comma`: `"17,5"` flagged by include 18-35.
  - `test_unlinked_criterion_silent`; `test_missing_project_json_or_criteria_silent`; `test_invalid_project_json_silent`.
  - `test_limit_change_applies_without_touching_participants_json`: rewrite `project.json` max, result changes.
  - `test_min_greater_than_max_warns_once_and_skips` (`PRISM603`); `test_unknown_criterion_id_warns_once` (`PRISM603`); `test_duplicate_ids_warn_and_first_wins`; `test_linked_column_missing_from_tsv_warns_once`.
- [ ] **Step 2: Run** `pytest tests/test_eligibility.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement** `check_eligibility` plus small private helpers per behavior in the spec's Validator section; one summary `PRISM602` line first when there are any violations ("N participant(s) outside eligibility criteria"). Add the `Criteria` array to the schema.
- [ ] **Step 4: Run** the test file → PASS. Also run the dual-tree one-liner above; it must print `src/eligibility.py`.
- [ ] **Step 5: Commit** `feat(eligibility): numeric criteria check and schema`.

### Task 2: Wire into the validator

**Files:**
- Modify: `app/src/runner.py` (in `validate_dataset`, inside the `run_prism` branch, after the top-level file registration near the `participants.tsv` check), `docs/ERROR_CODES.md` (add `PRISM602`, `PRISM603` under the 6xx table)
- Test: `tests/test_eligibility_validate_dataset.py`

**Interfaces:**
- Consumes: `check_eligibility(root_dir)` from Task 1.

- [ ] **Step 1: Failing test**: a minimal dataset (reuse a fixture/helper pattern from `tests/test_bids_validator.py` or build the smallest valid tree) with age 17 and include 18-35; `validate_dataset(root)` issues contain a `PRISM602` with level WARNING, and no new ERROR. Second test: `run_prism=False` → no eligibility issues.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Call** `check_eligibility` from `validate_dataset` only when `run_prism`, extend `issues`.
- [ ] **Step 4: Run** both test files → PASS; then `pytest tests -k "validator or runner" -q` for no regressions.
- [ ] **Step 5: Commit** `feat(eligibility): validate_dataset reports eligibility warnings`.

### Task 3: Link transport and suggestions

**Files:**
- Modify: `src/eligibility.py` (add `suggest_links`), the participants preview payload builder (find where `neurobagel_schema` is put into the preview response: `grep -n "neurobagel_schema" src/participants_backend.py app/src/web/blueprints/conversion_participants_*.py`), `app/src/cli/commands/participants.py` only if preview output needs the key
- Test: `tests/test_eligibility_links.py`

**Interfaces:**
- Produces: `suggest_links(criteria: list[dict], participants_schema: dict) -> dict[str, str]` mapping column name → criterion id when the column's `Annotations.IsAbout` term equals the criterion's `term` (compare after stripping any prefix difference only if the existing mapping code does the same; otherwise exact). Never suggests for criteria with `term: null`. Preview JSON (CLI `participants preview --json` and the Flask preview) gains `eligibility_suggestions: dict[str, str]`, `{}` without a `project.json` or criteria.

- [ ] **Step 1: Failing tests**: (a) `suggest_links` matches `age` column with `nb:Age` to criterion `age`; no suggestion for term-less criteria or unannotated columns. (b) `participants convert --neurobagel-schema '{"age":{"EligibilityCriterion":"age"}}'` writes `EligibilityCriterion` into `participants.json` (follow `tests/test_participants_cli.py` `_run_prism_tools`). (c) Merge into an existing `participants.json` keeps an existing link. (d) Preview JSON contains `eligibility_suggestions`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `suggest_links`; add the key to the preview payload.
- [ ] **Step 4: Run** `pytest tests/test_eligibility_links.py tests/test_participants_cli.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(eligibility): link transport and suggestions`.

### Task 4: Categorical criteria

**Files:**
- Modify: `src/eligibility.py`
- Test: `tests/test_eligibility.py` (add)

**Interfaces:**
- Consumes: the participants column's `Levels` (code → label, string or `{"Description": ...}` form: reuse `src/participants_levels.py` helpers if one resolves a label, else read both forms).

- [ ] **Step 1: Failing tests**: sex codes 1/2/3 with `Levels` 1=Female, 2=Male, 3=Other and criterion `exclude values ["Male"]` → every code `2` participant warned; `include values ["Female","Male"]` flags code 3; `test_label_compare_is_exact` (`male` ≠ `Male`, so no match); `test_linked_categorical_without_levels_warns_once` (`PRISM603`); value not in `Levels` for an include criterion is flagged.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the categorical branch beside the numeric one. **Step 4: Run** → PASS. **Step 5: Commit** `feat(eligibility): categorical criteria via Levels`.

### Task 5: Metadata form rows (Projects page)

**Files:**
- Create: `app/static/js/modules/projects/eligibility-criteria.js` (pure helpers: `criteriaFromRows(rows)`, `rowsFromCriteria(criteria)`, fixed term list from the spec: Age numeric; Sex, Handedness, Group/Diagnosis, Education level categorical; plus "Other measure")
- Modify: `app/templates/projects.html` (criteria list in the Eligibility section near `smEligInclusion`), `app/static/js/modules/projects/create-project.js:205` (add `Criteria` to the Eligibility payload), `app/static/js/modules/projects/metadata.js:184` (load it back), `app/src/project_manager.py:7190` only if it filters unknown keys
- Test: `app/static/js/modules/projects/eligibility-criteria.test.js`

**Interfaces:**
- Produces: `criteriaFromRows(rows) -> Criterion[]` (spec shape; drops incomplete rows), `rowsFromCriteria(criteria) -> row[]`; round trip is lossless.

- [ ] **Step 1: Failing vitest**: round trip for a numeric and a categorical criterion; incomplete row dropped; `id` generated unique and stable across a round trip.
- [ ] **Step 2: Run** `npx vitest run app/static/js/modules/projects/eligibility-criteria.test.js` → FAIL.
- [ ] **Step 3: Implement** the helpers, then wire the template, save and load. Add a Python test that a saved `project.json` keeps `Eligibility.Criteria` (extend an existing project-save test).
- [ ] **Step 4: Run** vitest and the Python test → PASS; open the page with the `run` skill and confirm adding/saving/reloading a row.
- [ ] **Step 5: Commit** `feat(eligibility): criteria rows in the study metadata form`.

### Task 6: Panel select

**Files:**
- Modify: `app/static/js/modules/converter/participants.js` (per-column select in the annotation panel; when building the neurobagel schema payload near `participants.js:2809` and `:3399`, add `EligibilityCriterion`), `app/templates/converter_participants.html`
- Create: `app/static/js/modules/converter/eligibility-link.js` (pure: `applyLinkToSchema(schema, column, criterionId)`, `unitMismatch(columnUnit, criterionUnit) -> boolean`)
- Test: `app/static/js/modules/converter/eligibility-link.test.js`
- Modify: `app/static/js/modules/converter/participants-replace-policy.js` (`REPLACE_CONFIRMATION_MESSAGE` also names eligibility links)

**Interfaces:**
- Consumes: `eligibility_suggestions` from Task 3's preview payload; criteria list from `project.json` via the existing project-state loader.

- [ ] **Step 1: Failing vitest**: `applyLinkToSchema` sets/removes the key without touching `Annotations`; `unitMismatch("years","months") === true`, `unitMismatch("","years") === false`; the replace message contains "eligibility".
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**, pre-selecting from `eligibility_suggestions` (user still confirms) and showing both units. **Step 4: Run** vitest → PASS; check in the running app with the FitCog files. **Step 5: Commit** `feat(eligibility): link a column to a criterion in the participants panel`.

### Task 7: Docs and the assignment example

**Files:**
- Modify: `docs/studio/projects.md`, `docs/studio/converter_participants.md`, `docs/ERROR_CODES.md` (if not complete), `examples/assignment_first_project/project_metadata.html` (Eligibility rows: Age include 18-35 years), `examples/assignment_first_project/moodle_assignment.md` (one extra step: link age to the criterion, then run the validator and expect no warnings; edit one value to 17 to see a warning)
- Test: `tests/test_docs_links.py` style existing docs check, if any, must still pass

- [ ] **Step 1:** Write the doc sections; mention warning-only and run-during-collection use.
- [ ] **Step 2: Run** the full suite `pytest -q` and `npx vitest run` → PASS.
- [ ] **Step 3: Commit** `docs(eligibility): usage and assignment example`.

Before merging: run `/ponytail:ponytail-audit` on the branch per CLAUDE.md, apply worthwhile findings, rerun tests, then finish the branch.
