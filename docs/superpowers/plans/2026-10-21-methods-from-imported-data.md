# Methods From Imported Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The methods draft lists every instrument/acquisition found in the dataset per session, infers session order and timing from the data, and marks unknowns with `[please add: ...]`.

**Architecture:** `src/methods_project.py` gains `discover_sessions(project_path)`, returning session dicts in the same shape as `project.json` `Sessions`, and `build_methods` uses them when `project.json` declares none. `generate_full_methods` (`app/src/reporting.py`) already renders `Sessions`; it only learns to word unordered sessions, state per-instrument counts and emit placeholders. CLI and GUI share `build_methods`, so no GUI logic is added.

**Tech Stack:** Python stdlib (`csv`, `datetime`, `re`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-21-methods-from-imported-data-design.md`

## Global Constraints

- Session labels are free-form strings, never normalized or coerced; comparison is exact string equality (CLAUDE.md).
- Timing comes from `acq_time` in `sessions.tsv` / `*_scans.tsv` only; MRI sidecar dates are scrubbed and are not a source.
- Unknown facts are omitted or written as `[please add: <what>]`; never invented. Placeholders appear in the preview and in every export (they are part of the markdown).
- `app/src/reporting.py` is the live generator, `src/methods_project.py` the single entry point. Run `python3 -c "import src.methods_project as m; print(m.__file__)"` before editing.
- TDD: each test is seen failing first. Every new function has its own test.
- Run `/ponytail:ponytail-audit` before merging; work on a branch, not `main`.

## Review Focus

- Dataset with no `ses-*` folders: one occasion, no ordinal wording, no timing placeholder.
- Non-numeric labels (`pre`, `post`): text makes no first/second claims; a warning is emitted.
- Labels `1` and `01` in one dataset: two distinct sessions, never merged.
- `sessions.tsv` with `n/a` or empty `acq_time`: no timing, no crash.
- Instrument present for only some participants: count stated, not "all".

---

### Task 1: Discover sessions and per-instrument counts

**Files:**
- Modify: `src/methods_project.py` (next to `discover_tasks`)
- Test: `tests/test_methods_project.py`

**Interfaces:**
- Consumes: `resolve_bids_rawdata_root(project_path)` from `src.environment_mri_scan`.
- Produces: `discover_sessions(project_path: Path) -> list[dict]`. Each dict: `{"id": "ses-<label>", "label": "<label>", "tasks": [{"task": str, "n": int}], "ordered": bool}`; no-session datasets give one dict with `id` and `label` `""`. Order: if every label is all digits, numeric order; otherwise lexical order. `ordered` is true only for the all-digit case or a single session.

- [ ] **Step 1: Write failing tests** `test_discover_sessions_groups_tasks_and_counts`, `test_discover_sessions_keeps_1_and_01_distinct` (two sessions, labels `"1"` and `"01"`), `test_discover_sessions_non_numeric_unordered` (`pre`, `post` → `ordered` False), `test_discover_sessions_without_session_folders` (one dict, label `""`, `ordered` True). Build files like `sub-01/ses-1/survey/sub-01_ses-1_task-ads_survey.tsv`.
- [ ] **Step 2: Run** `pytest tests/test_methods_project.py -k discover_sessions -v`; expected FAIL (`discover_sessions` undefined).
- [ ] **Step 3: Implement** `discover_sessions`, reusing the globbing/regex of `discover_tasks`; `n` is the number of distinct subjects with that task in that session. Refactor so both functions share one file scan.
- [ ] **Step 4: Run** the same command; expected PASS.
- [ ] **Step 5: Commit** `feat(methods): discover sessions and instrument counts from the dataset`.

### Task 2: Infer timing from sessions.tsv / scans.tsv

**Files:**
- Modify: `src/methods_project.py`
- Test: `tests/test_methods_project.py`

**Interfaces:**
- Consumes: `discover_sessions` (Task 1).
- Produces: `add_session_timing(project_path: Path, sessions: list[dict]) -> None`, mutating each session (except the earliest) with `"timingRelativeToBaseline": {"Value": int, "Unit": "days"}` using the median `acq_time` per session label across subjects; earliest is baseline. Sessions with no parsable `acq_time` get no key.

- [ ] **Step 1: Write failing tests** `test_timing_from_sessions_tsv_gives_days_after_baseline` (two subjects, ses-1 on 2025-01-01, ses-2 on 2025-01-15 → `Value` 14), `test_timing_ignores_na_and_empty_acq_time` (no key, no exception), `test_timing_absent_without_tsv`.
- [ ] **Step 2: Run** `pytest tests/test_methods_project.py -k timing -v`; expected FAIL.
- [ ] **Step 3: Implement** with `csv.DictReader` (tab) and `datetime.fromisoformat`; read `sub-*/sub-*_sessions.tsv` first, fall back to `*_scans.tsv`.
- [ ] **Step 4: Run** same; expected PASS.
- [ ] **Step 5: Commit** `feat(methods): infer session timing from acq_time`.

### Task 3: Wire into build_methods; wording, counts, placeholders

**Files:**
- Modify: `src/methods_project.py` (`build_methods`), `app/src/reporting.py` (Procedure block, Measures block, `methods_warnings`)
- Test: `tests/test_methods_project.py`, `tests/test_reporting_methods_generation.py`

**Interfaces:**
- Consumes: `discover_sessions`, `add_session_timing`.
- Produces: `build_methods` sets `project_data["Sessions"]` from them when `project.json` has no `Sessions` (declared ones win). Generator rules: `ordered` false → no "first/second session" wording, sessions named by label; instrument sentences state `n` ("completed by *n* = 40 participants"); more than one session with no timing → sentence `[please add: time between sessions]`; an instrument with no template found → `[please add: reference for <task>]`; unordered sessions → one entry in `warnings`.

- [ ] **Step 1: Write failing tests** `test_build_methods_procedure_lists_surveys_per_session` (md contains both labels and the instrument per session), `test_methods_unordered_sessions_make_no_ordinal_claim` (no "first session" in md, one warning), `test_methods_states_participant_count_per_instrument`, `test_methods_placeholder_for_unknown_timing` and `..._for_missing_template`, `test_declared_sessions_override_inference`.
- [ ] **Step 2: Run** `pytest tests/test_methods_project.py tests/test_reporting_methods_generation.py -v`; expected the new tests FAIL.
- [ ] **Step 3: Implement** in `build_methods` (merge) and `generate_full_methods` (wording rules above); keep new generator logic in small helper functions, not inline growth.
- [ ] **Step 4: Run** same; expected all PASS.
- [ ] **Step 5: Commit** `feat(methods): procedure per session with counts and placeholders`.

### Task 4: CLI/GUI parity and full verification

**Files:**
- Test: `tests/test_cli_methods.py`, `tests/test_projects_methods_handlers.py`

**Interfaces:**
- Consumes: `build_methods` (Task 3).

- [ ] **Step 1: Write failing tests** `test_cli_methods_includes_placeholders_and_sessions` and a handler test that the GUI response `md` equals the CLI output for the same project.
- [ ] **Step 2: Run** `pytest tests/test_cli_methods.py tests/test_projects_methods_handlers.py -v`; expected FAIL if parity breaks, otherwise PASS immediately, which proves the shared entry point already carries it.
- [ ] **Step 3: Run the full suite** `pytest -q` and `python tests/verify_repo.py --check dual-tree-drift --no-fix`; expected all PASS.
- [ ] **Step 4: Commit** `test(methods): CLI/GUI parity for session procedure`.
