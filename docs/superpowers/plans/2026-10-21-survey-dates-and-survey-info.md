# Survey Dates And Survey Info Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Session intervals in the methods draft come from per-subject survey dates stored at import; those dates never leave the lab in an export; each survey in the draft gets language, version, administration and mean completion time.

**Architecture:** The LimeSurvey import writes `SurveyStartDate`. One new module `src/survey_dates.py` owns removing it (used by the ZIP export per file and by the plain-folder export per tree). `add_session_timing` becomes per-subject. A `survey_info` summary (durations from the data) is passed into `generate_full_methods` like `acquisition`.

**Tech Stack:** Python stdlib (`csv`, `json`, `statistics`, `datetime`), pandas (already used by the importer), pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-survey-dates-and-survey-info-design.md`

## Global Constraints

- `SurveyStartDate` is `YYYY-MM-DD`; column name exactly `SurveyStartDate`; source `startdate`, fallback `datestamp`.
- A shared dataset must never contain a survey date: both `export_project` (unconditionally) and `export_project_to_plain_folder` remove the column from every survey TSV and its sidecar entry. If convenience conflicts, the gate wins.
- `publish_to_server` is unchanged; `sessions.tsv`/`scans.tsv` `acq_time` is not stripped; `SurveyStartTime` stays.
- Session labels stay free-form; exact string comparison.
- Text files are never annexed (CLAUDE.md): rewrite exported copies in place, never the source project.
- `app/src/web/export_project.py` and `src/` are a dual tree: confirm which file answers with `python3 -c "import src.survey_dates as m; print(m.__file__)"`; the new module lives only in `src/`.
- TDD; every new function has its own test; `/ponytail:ponytail-audit` before merge; work on a branch.

## Review Focus

- Export with `anonymize=False`: ZIP still has no `SurveyStartDate` column or sidecar key.
- A survey TSV where the column is the last/only extra column, or absent: rewritten correctly / left byte-identical.
- Subject with one session only, or sessions with `n/a` dates: no crash, no timing for them.
- Symlinked or annexed TSV in the plain-folder copy: source file untouched, copy stripped.
- `SurveyDuration` with empty or non-numeric cells: skipped, mean over the numeric ones.

---

### Task 1: Import writes SurveyStartDate

**Files:**
- Modify: `src/converters/limesurvey.py` (duration block ~1655-1669; schema blocks ~1732-1740 and ~1805-1816)
- Test: `tests/test_limesurvey_utils.py`

**Interfaces:**
- Produces: `add_survey_time_columns(df: pd.DataFrame) -> None` in `limesurvey.py`, adding `SurveyDuration`, `SurveyStartTime` and `SurveyStartDate` in place when `startdate` (else `datestamp`) and `submitdate` exist; unparsable dates give empty cells. Both schema injection sites also add `"SurveyStartDate": {"Description": "Start date of the LimeSurvey session (YYYY-MM-DD)", "Units": "date"}`.

- [ ] **Step 1: Write failing tests** `test_add_survey_time_columns_writes_start_date` (startdate `2025-03-04 10:15:00`, submitdate 10 minutes later → `SurveyStartDate` `"2025-03-04"`, `SurveyDuration` 10.0, `SurveyStartTime` `"10:15:00"`), `test_add_survey_time_columns_falls_back_to_datestamp`, `test_add_survey_time_columns_bad_date_is_empty`; and extend the two existing schema-capture tests with `assert "SurveyStartDate" in ads_schema` and the df-capture one with `"SurveyStartDate" in captured["df"].columns`.
- [ ] **Step 2: Run** `pytest tests/test_limesurvey_utils.py -v`; expected the new/extended tests FAIL.
- [ ] **Step 3: Implement** by extracting the inline duration block into `add_survey_time_columns` (behaviour of the existing two columns unchanged) and adding the date column and the two schema entries.
- [ ] **Step 4: Run** same; expected PASS.
- [ ] **Step 5: Commit** `feat(import): store the survey start date in the survey TSV`.

### Task 2: Remove survey dates from every export

**Files:**
- Create: `src/survey_dates.py`
- Modify: `app/src/web/export_project.py` (`_json_bytes`, `_tsv_bytes`, the two TSV dispatch branches ~729 and ~864), `app/src/project_manager.py` (`export_project_to_plain_folder`, after the copy, before returning)
- Test: `tests/test_survey_dates.py`

**Interfaces:**
- Produces in `src/survey_dates.py`: `SURVEY_DATE_COLUMN = "SurveyStartDate"`; `has_survey_date(tsv_path: Path) -> bool` (header check only); `drop_survey_date_tsv(text: str) -> str` (removes the column, keeps everything else and `\n` line endings); `drop_survey_date_sidecar(data: dict) -> dict` (removes the top-level key); `strip_survey_dates_in_tree(root: Path) -> int` (rewrites every `*/survey/*.tsv` and `*.json` under `root` in place, replacing symlinks with real files, returns files changed).

- [ ] **Step 1: Write failing tests** in `tests/test_survey_dates.py`: unit tests for each helper (column in the middle/last/absent; sidecar key); `test_zip_export_drops_survey_date_without_anonymize` (build a tiny project with `sub-01/survey/…_survey.tsv` containing the column and its sidecar, call `export_project(..., anonymize=False)`, open the ZIP: no `SurveyStartDate` in any TSV header or JSON); the same with `anonymize=True`; `test_plain_folder_export_drops_survey_date_and_keeps_source` (source file still has the column); `test_strip_replaces_symlink_without_touching_target`.
- [ ] **Step 2: Run** `pytest tests/test_survey_dates.py -v`; expected FAIL (module missing).
- [ ] **Step 3: Implement** the module; in `_json_bytes` apply `drop_survey_date_sidecar` for every dict; make the zip TSV branches take `has_survey_date(source) or (anonymize and participant_mapping)` and apply `drop_survey_date_tsv` inside `_tsv_bytes`; call `strip_survey_dates_in_tree(export_path)` in the plain-folder export after the copy.
- [ ] **Step 4: Run** `pytest tests/test_survey_dates.py tests -k "export" -q`; expected PASS.
- [ ] **Step 5: Commit** `feat(export): never ship survey dates in a shared copy`.

### Task 3: Per-subject session timing

**Files:**
- Modify: `src/methods_project.py` (`add_session_timing`, `_acq_times`)
- Test: `tests/test_methods_project.py`

**Interfaces:**
- Consumes: `SURVEY_DATE_COLUMN` (Task 2), `discover_sessions` (existing).
- Produces: same `add_session_timing(project_path: Path, sessions: list[dict]) -> None`; now per subject: offset = days from that subject's earliest dated session to each of their later sessions; a session's `timingRelativeToBaseline` is `{"Value": round(median offset), "Unit": "days"}` over subjects with both sessions. Sources in order, first with any data wins: `SurveyStartDate` in `sub-*/**/survey/*.tsv`, `*_sessions.tsv` `acq_time`, `*_scans.tsv` `acq_time`.

- [ ] **Step 1: Write failing tests** `test_timing_from_survey_start_date_is_per_subject` (sub-01: ses-1 Jan 1, ses-2 Jan 15; sub-02: ses-1 Jan 10, ses-2 Jan 31 → median of 14 and 21 = 17.5 → `18`; absolute medians would give a different value, pinning the new behaviour), `test_timing_skips_subject_with_one_dated_session`, `test_timing_survey_date_beats_sessions_tsv`; existing timing tests keep passing.
- [ ] **Step 2: Run** `pytest tests/test_methods_project.py -k timing -v`; expected new tests FAIL.
- [ ] **Step 3: Implement** by reading `(subject, session, epoch seconds)` triples from the three sources and aggregating per subject; keep the helper small and shared by the sources.
- [ ] **Step 4: Run** same; expected PASS.
- [ ] **Step 5: Commit** `feat(methods): session timing from per-subject survey dates`.

### Task 4: Survey info in the draft

**Files:**
- Modify: `src/methods_project.py` (`build_methods`), `app/src/reporting.py` (Measures block)
- Test: `tests/test_methods_project.py`, `tests/test_reporting_methods_generation.py`

**Interfaces:**
- Consumes: `discover_sessions`-style file scan.
- Produces: `survey_durations(project_path: Path) -> dict[str, dict]` in `methods_project.py`, `{task: {"mean": float, "sd": float | None, "n": int}}` in minutes from `SurveyDuration` (non-numeric/empty skipped; tasks with no values omitted). `generate_full_methods(..., survey_info: dict | None = None)`; per instrument, in non-brief detail, after the opening sentence: `Technical.Language` ("Language: German."), `Study.Version` ("Version: 10-item."), administration from `Technical.AdministrationMethod`/`Respondent`/`SoftwarePlatform` joined as one sentence, and "The mean completion time was *M* = 4.2 minutes (*SD* = 1.1, *n* = 40)." from `survey_info`. Unknown parts are omitted, never invented. `build_methods` passes `survey_durations(project_path)`.

- [ ] **Step 1: Write failing tests** `test_survey_durations_mean_sd_n_skips_bad_cells`, `test_methods_states_language_version_and_administration`, `test_methods_states_mean_completion_time`, `test_methods_omits_survey_info_that_is_unknown`, `test_brief_detail_omits_survey_info`.
- [ ] **Step 2: Run** `pytest tests/test_methods_project.py tests/test_reporting_methods_generation.py -v`; expected new tests FAIL.
- [ ] **Step 3: Implement** `survey_durations` and the sentences; keep the sentence assembly in one small helper function in `reporting.py`.
- [ ] **Step 4: Run** same plus `tests/test_cli_methods.py tests/test_projects_methods_handlers.py`; expected PASS.
- [ ] **Step 5: Run full suite** `pytest -q` and `python tests/verify_repo.py --check dual-tree-drift --no-fix`; expected all PASS. Commit `feat(methods): survey language, version, administration and completion time`.
