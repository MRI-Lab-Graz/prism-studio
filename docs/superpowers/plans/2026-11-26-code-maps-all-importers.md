# Code Maps for All Importers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (chosen: one session). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every importer that takes a participant from data uses the project's code maps, with one shared implementation.

**Architecture:** The survey-only logic (open maps, warnings, git exclusion, resolve all rows) moves into `src/code_maps.py`. Each importer calls it once, before anything is written. Studio gets no new logic.

**Tech Stack:** Python standard library, pandas as already used, pytest.

**Spec:** [docs/superpowers/specs/2026-11-26-code-maps-design.md](../specs/2026-11-26-code-maps-design.md), including "Raw-file imports".

**Branch:** `feat/code-maps` (continue; merge only when this plan is done).

## Global Constraints

- THE CLI EXECUTES, STUDIO ONLY TRIGGERS: no logic in `app/src/web/**` or JavaScript.
- Prefix = modality: `biometrics_`, `environment_`, `biosample_`, `participants_`, `physio_`, `eyetracking_`, any other modality name alike. No hand-written modality list.
- Same rules and same message texts as the survey import (task, session, general; disagreement stops; one row one person).
- A value no map lists stops the import; nothing is written. Raw files only: a value that already is a mapped participant number stays.
- An explicitly named ID column is never swapped. An explicit manual participant (`participant_override`, `id_overrides`) is not looked up.
- Session labels are the ones written to the dataset, exact strings.
- No typed code may reach a file name, folder name, `participants.tsv`, log line or note of a successful import when maps exist.
- Invented codes only.

## Review Focus

1. A map with only a header or empty targets: every importer stops (no raw code written). Test in each task.
2. Fallback numbering (environment `sub-01` for an empty cell): with maps, an empty cell stops. (Task 3)
3. Preview and dry run: same messages and same stops as the real run, nothing written. (each task)
4. One bad row or file late in the input: nothing at all is written. (each task)
5. Existing-participant matching (biometrics `existing_participant_ids`) must not turn a mapped ID into another one. (Task 2)

Test command for every task: `PRISM_SKIP_VENV_CHECK=1 /Users/karl/work/github/prism-studio/.venv/bin/python -m pytest -q <files>`

---

### Task 1: One implementation for all importers

**Files:** Modify `src/code_maps.py`, `app/src/converters/survey_participants_logic.py`; Test `tests/test_code_maps_project.py`

**Interfaces (produces):**

```python
class UnknownCodeError(CodeMapError):
    codes: list[str]          # every unlisted value, sorted

class ProjectCodeMaps:
    @classmethod
    def open(cls, project_root, modality, known_tasks=None) -> "ProjectCodeMaps | None"
    # None: no project, no maps, or inside without_project_code_maps().
    # Excludes the maps from git; collects the tracked, unknown-task and unknown-session warnings
    # (known sessions come from src.session_map); raises on a task spelled in the wrong case.
    def resolve(self, code, tasks=(), session=None) -> str | None
    def resolve_all(self, rows, keep_targets=False) -> list[str]
    # rows: sequence of (code, tasks, session); raises UnknownCodeError after looking at all rows.
    # keep_targets: a value equal to a participant of any loaded map ("004" or "sub-004") stays.
    def notes(self) -> list[str]   # warnings, then "Applied code map <file>: <n> code(s)."
```

- [ ] Tests: `open` returns None without maps; excludes from git; `resolve_all` reports all unknown values at once; `keep_targets` true and false; empty map gives `UnknownCodeError`; notes text equals the survey's.
- [ ] Run, expect FAIL.
- [ ] Implement; make the survey import use `ProjectCodeMaps` and delete its own copy. `MissingIdMappingError` stays the survey's error type.
- [ ] Run new tests and `tests/test_survey_code_maps.py tests/test_code_maps_review.py tests/test_cli_studio_parity.py`, expect PASS.
- [ ] Commit `refactor: one place applies project code maps`

---

### Task 2: Biometrics

**Files:** Modify `src/converters/biometrics.py` (`convert_biometrics_table_to_prism_dataset`, IDs at ~298-345 and ~399); Test `tests/test_biometrics_code_maps.py`

**Behaviour:** map the ID column once, before `_resolve_sub_id` and before the cleaning notes. Tasks of a row: the exported tasks that have a value column in the table (all of them, also when `tasks_to_export` narrows). Session: the label written (`session_ids[...]`). A mapped ID is not passed through the existing-participant matcher. Notes go to the result warnings.

- [ ] Tests: general map; `task-` map for one test with a split row stops, also with `tasks_to_export`; `ses-` map; unlisted code stops with nothing written; empty map stops; `participants.tsv` holds mapped IDs only; no code appears in warnings; CLI/Studio parity case.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit `feat(biometrics): use project code maps`

---

### Task 3: Environment

**Files:** Modify `src/environment_conversion.py` (`perform_environment_conversion`, ~850-1000); Test `tests/test_environment_code_maps.py`

**Behaviour:** map `participant_col` before pilot selection and before row processing. No tasks. Session as written. With maps, an empty or unlisted cell stops; the `sub-NN` fallback is not used. `participant_override` without a participant column is unchanged.

- [ ] Tests: general and `ses-` map; unlisted; empty cell; pilot subject run maps the same; override unchanged; nothing written on stop; no provider request is made when the maps stop the run; parity case.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit `feat(environment): use project code maps`

---

### Task 4: Biosample

**Files:** Modify `src/biosample_import.py` (`import_biosample`, ~130-180); Test `tests/test_biosample_code_maps.py`

**Behaviour:** the `participant_id` column holds the code. `task-` selects by panel name (first confirm the panel is the `task-` label of the written files; if it is not, no task scope for biosample and ledger it). Rows of different panels are separate rows, so each follows its own map. Errors go to `res.errors` with the data row number.

- [ ] Tests: general, `ses-`, panel map; unlisted reported per row and nothing written; empty map; dry run; parity case (`tests/test_biosample_cli_studio_parity.py` pattern).
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit `feat(biosample): use project code maps`

---

### Task 5: Participants

**Files:** Modify `src/participants_converter.py` (`convert_participant_data`, ~390-545) and the preview and merge paths of `src/participants_backend.py` that read IDs from the input file; Test `tests/test_participants_code_maps.py`

**Behaviour:** only the general `participants_code_map.tsv`; a `task-` or `ses-` participants map stops with `participants maps cannot be narrowed by task or session`. Map the input's ID column where the input table is loaded, so preview, convert and merge see the same IDs. Existing `participants.tsv` values are not looked up. This task is the one most likely to need a ruling: list every path that reads input IDs in the ledger first.

- [ ] Tests: convert, preview and merge each give mapped IDs; unlisted stops; narrowed map stops; empty map stops; session-resolution decisions still apply; `participants.tsv` and the report contain no code; parity case.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit `feat(participants): use project code maps`

---

### Task 6: Raw files

**Files:** Modify `src/batch_convert.py` (`batch_convert_folder`); Test `tests/test_raw_file_code_maps.py`

**Behaviour:** per file, maps of the file's target modality (the same name used for its output folder); label = `sub-` part without prefix; session = the written one; task = `task-` part. `keep_targets=True`. Resolve every file before the first one is converted; an unknown label raises and nothing is written. The output name, the sidecar, `participants.tsv` and the log use the mapped participant. `.lsa` batch stays unchanged (refused in projects).

- [ ] Tests: code in the name is translated (physio and a generic eyetracking file); `sub-004` stays; unknown stops with nothing written even when it is the last file; `task-`/`ses-` maps; dry run; a modality without a map is unchanged; two files that end up with the same target name are reported as the existing conflict; parity case against the Studio call in `conversion_physio_handlers.py`.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit `feat(raw files): use project code maps`

---

### Task 7: Close the gaps and document

**Files:** Modify `tests/test_importers_use_code_maps.py`, `docs/CODE_MAPS.md`

- [ ] Move every importer to `USES_CODE_MAPS`; `KNOWN_GAPS` becomes empty; `src/project_registration.py` goes to an `EXEMPT` entry ("reads no participant IDs"). Add a test that every importer of `tests/test_importers_use_session_policy.FOLLOWS_POLICY` is classified.
- [ ] Docs: replace the survey-only sentence; add the per-modality table, the raw-file rule, and that participants maps cannot be narrowed.
- [ ] Run the whole suite; compare failures with the 6 non-browser and 72 browser failures of the unchanged code.
- [ ] Commit `docs: code maps for every importer`

### Then

One review of the branch (Sonnet), fix pass. Before merge: `/ponytail:ponytail-audit`, `/code-review`, `/security-review`.
