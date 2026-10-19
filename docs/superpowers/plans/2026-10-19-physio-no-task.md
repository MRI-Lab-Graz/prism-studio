# Physio without task / no `events/` folder / no `physiological` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `physio/` holds task-free PRISM recordings only (EDF, unchanged); task-bound physio is written to `beh/`, `func/` or `eeg/` as BIDS `_physio.tsv.gz` + flat sidecar; `events/` folder and `physiological` alias are retired.

**Architecture:** Rules live in `app/schemas/stable/entities.schema.json` (loaded by `src/entity_rules.py`). One backend helper decides the target folder; the three physio writers (batch converter, `convert physio` CLI, renamer/organizer) and the GUI call it. BIDS output never needs pyedflib (it is unreliable on Windows): `.edf` sources are read by a small pure-Python EDF reader, and `convert_varioport` gets one narrow seam (a collector with the same four methods as `pyedflib.EdfWriter`) so `.raw/.vpd` can be written as BIDS without ever importing pyedflib. Task-free EDF output keeps using pyedflib exactly as today.

**Tech Stack:** Python, Flask, pytest, numpy. pyedflib stays optional and is needed only for writing task-free EDF (unchanged).

**Spec:** `docs/superpowers/specs/2026-10-19-physio-no-task-design.md` (approved 2026-10-19)

## Global Constraints

- Work only in the worktree `/Users/karl/work/github/prism-studio-modalities` (branch `feat/physio-no-task-drop-events-folder`). Never touch `/Users/karl/work/github/prism-studio` (uncommitted file-picker work lives there).
- Run tests with the main checkout's interpreter: `/Users/karl/work/github/prism-studio/.venv/bin/python -m pytest <path> -q` from the worktree. First check `python -c "import src; print(src.__file__)"` resolves inside the worktree; if not, set `PYTHONPATH` to the worktree.
- TDD: each failing test is run and seen failing before code (CLAUDE.md).
- Every command lives in backend/CLI; GUI only passes values through (CLAUDE.md "One implementation").
- Session/subject labels are exact strings; never pad or normalize (`ses-1` ≠ `ses-01`).
- Destination values are exactly `beh`, `func`, `eeg`. No default destination, ever.
- Task-free output: `sub-X[_ses-Y]/physio/sub-X[_ses-Y]_recording-<r>_physio.edf|json`, format unchanged.
- Task-bound output: `sub-X[_ses-Y]/<dest>/sub-X[_ses-Y]_task-<t>_recording-<r>_physio.tsv.gz|json`; tsv.gz has no header row; sidecar is flat with `SamplingFrequency`, `StartTime`, `Columns`; no EDF, no PRISM nested sidecar.
- No task-bound code path may import pyedflib (Windows wheels are unreliable). Tests for task-bound output must run without pyedflib installed; no `importorskip`.
- New backend modules live only in top-level `src/` (no `app/src/` twin). After touching any `app/src/` non-route file run `find src -name '<file>'` (dual-tree rule in CLAUDE.md).
- Text-format files are never annexed (not relevant to code here; don't touch `.gitattributes` logic).
- Before merge: run `/ponytail:ponytail-audit`, apply what's worth it, re-run tests (CLAUDE.md).

## Review Focus

1. Batch folder mixing task-free and task-bound files with no `--destination`: job fails before writing anything (test in Task 4).
2. `.json` sidecar named `..._task-x_physio.json` inside `physio/` is flagged like the data file (Task 2).
3. Project whose `project.json` pins `SchemaVersions.events` still resolves; `modality-version` can still pin `events` (Task 1).
4. Task-bound conversion with pyedflib absent (`sys.modules["pyedflib"] = None`): succeeds, for both an `.edf` source and the Varioport collector (Tasks 3, 4). A truncated/non-EDF `.edf` source gives a clear error and writes nothing.
5. `--dry-run` batch with task-bound files writes nothing into the output folder (Task 4).

---

### Task 1: Rules file and entity_rules

**Files:**
- Modify: `app/schemas/stable/entities.schema.json`, `src/entity_rules.py`
- Modify tests: `tests/test_entity_rules.py`, `tests/test_entity_rules_allowed.py`, `tests/test_unit.py:399`, `tests/test_schema_manager_modality_versions.py:47`, `tests/test_modality_extension.py:100`, `tests/test_modality_proposal_check.py:34`, `tests/test_bids_integration.py:73`, `tests/verify_repo.py:1590`
- Test: `tests/test_entity_rules.py`

**Interfaces:**
- Produces: `ModalityRule.folder: bool` (default `True`, read from JSON key `"folder"`); `EntityRules.aliases` is `{}`; `physio.allowed_entities == ("acq", "run", "recording")`; `"events"` rule has `folder False`; `rules.project_modalities` excludes `events`.

- [ ] **Step 1: Failing tests** in `tests/test_entity_rules.py`: `test_physiological_alias_is_gone` (`load_entity_rules().aliases == {}`); `test_events_is_not_a_project_folder` (`"events" not in rules.project_modalities` and `rules.modalities["events"].folder is False`); `test_physio_rejects_task` (`check_entities("sub-01_task-x_recording-ecg_physio", rules.modalities["physio"].allowed_entities, rules.entity_order)` is non-empty, `"sub-01_ses-pre_recording-ecg"` gives `[]`); `test_events_pin_still_resolves` (`"events" in modality_names()` from `src.modality_versions`).
- [ ] **Step 2:** Run `pytest tests/test_entity_rules.py -q`; expect these 4 to FAIL.
- [ ] **Step 3:** Implement: delete `"aliases"` block; add `"folder": false` to `events`; add `"allowedEntities": ["acq","run","recording"]` to `physio`; add the `folder` field to `ModalityRule.from_json`; `project_modalities` also requires `rule.folder`. Keep the `events` entry otherwise untouched so `modality_names()` still lists it.
- [ ] **Step 4:** Update the existing tests/checks listed under Files that assert the alias (`schemas["physiological"]`, alias in proposal check, expected folder sets). Default for the proposal checker: drop the alias branch. Update `tests/test_entity_rules_allowed.py::test_existing_modalities_have_no_allowed_entities_yet` to exclude `physio`.
- [ ] **Step 5:** Run `pytest tests/test_entity_rules.py tests/test_entity_rules_allowed.py tests/test_unit.py tests/test_schema_manager_modality_versions.py tests/test_modality_extension.py tests/test_modality_proposal_check.py tests/test_bids_integration.py tests/test_modality_versions.py -q`; expect PASS. Fix residual `physiological` fallout in `src/schema_manager.py` if it still builds an alias entry.
- [ ] **Step 6:** Commit `feat(rules): retire physiological alias, events folder; physio is task-free`.

### Task 2: Validator and runner

**Files:**
- Modify: `app/src/runner.py` (lines ~811, ~930, ~1030), `app/src/validator.py` (~328, ~400), `app/src/stats.py` (~118, ~160), `app/src/issues.py` (~364), `app/src/bids_validator.py` (~136–142), `app/src/web/upload.py` (~62–69)
- Test: `tests/test_physio_no_task_validation.py` (new)

**Interfaces:**
- Produces: `RETIRED_FOLDERS: dict[str, str]` in `app/src/runner.py` mapping `"events"` and `"physiological"` to their hint text; `validate_filename` returns an ERROR for a `task-` entity in a `physio` filename whose message contains `beh`, `func` and `eeg`.

- [ ] **Step 1: Failing tests** (build a tiny dataset in `tmp_path`, call `runner.validate_dataset(str(root), run_prism=True, run_bids=False)` as `tests/test_runner.py` does): `test_events_folder_is_flagged` (`sub-01/events/sub-01_task-x_events.tsv` → ERROR mentioning "events" and "func"); `test_physiological_folder_is_flagged` (message mentions "physio"); `test_task_in_physio_filename_is_error` (data file `sub-01_task-x_recording-ecg_physio.edf`); `test_task_in_physio_sidecar_is_error` (the `.json` twin, Review Focus 2); `test_task_free_physio_is_clean` (`sub-01_ses-pre_recording-ecg_physio.edf` + `.json` with minimal valid sidecar, no filename errors); `test_events_tsv_in_func_still_checked` (a `func/sub-01_task-x_events.tsv` without sidecar still produces the events-sidecar issue it produced before this change).
- [ ] **Step 2:** Run `pytest tests/test_physio_no_task_validation.py -q`; expect FAIL (first five).
- [ ] **Step 3:** Implement `RETIRED_FOLDERS` and emit `("ERROR", f"Folder '{item}' is not a PRISM modality: {hint}", item_path)` in `_validate_subject` and `_validate_session` before the `item in MODALITY_PATTERNS` branches, then skip that folder. Remove `"physiological"` from every list/tuple/`in [...]` in the files above; remove `"events"` from folder lists in `issues.py` hint set, `bids_validator.py` `prism_ignore_folders` (keep `physio`), `upload.py` `RESTRICTED_FOLDER_NAMES` only where it means a folder (builder confirms each). The task-in-physio message comes from the existing `check_entities` path in `validate_filename`; append the destination hint when the offending entity is `task`.
- [ ] **Step 4:** Run the new file plus `tests/test_runner.py tests/test_validator*.py tests/test_issues*.py tests/test_bids_validator*.py -q`; expect PASS.
- [ ] **Step 5:** `find src -name validator.py -o -name runner.py -o -name stats.py -o -name issues.py` and confirm which tree answers (CLAUDE.md check). Commit `feat(validator): flag events/ and physiological/ folders, reject task- in physio/`.

### Task 3: Destination helper and BIDS physio writer

**Files:**
- Create: `src/physio_bids.py`
- Modify: `src/batch_convert.py` (add helper next to constants)
- Test: `tests/test_physio_bids.py` (new)

**Interfaces:**
- Produces in `src/batch_convert.py`: `PHYSIO_TASK_DESTINATIONS = ("beh", "func", "eeg")` and `physio_target_folder(task: str | None, destination: str | None) -> str` (returns `"physio"` when `task` is falsy — a stray destination is ignored; returns `destination` when valid; raises `ValueError` mentioning `beh, func, eeg` when `task` is set and `destination` is missing or invalid).
- Produces in `src/physio_bids.py`:
  `write_bids_physio(channels: dict[str, np.ndarray], *, sampling_frequency: float, start_time: float, out_base: Path, extra_meta: dict | None = None) -> list[Path]` — writes `<out_base>.tsv.gz` (no header, columns in dict order, equal-length channels) and `<out_base>.json` (`SamplingFrequency`, `StartTime`, `Columns`, plus `extra_meta`); `out_base` ends with `_physio`.
  `read_edf(edf_path: Path) -> tuple[dict[str, np.ndarray], dict[str, float], float]` — pure-Python (struct + numpy) reader for EDF/EDF+: returns physical-unit channels by label, sampling rate by label, and `StartTime` 0.0 (BIDS: seconds relative to the first data row); skips the `EDF Annotations` channel; raises `ValueError("not a valid EDF file: ...")` on a bad/truncated header.
  `edf_to_bids_physio(edf_path: Path, out_dir: Path, stem_prefix: str, recording_label: str) -> list[Path]` — `read_edf`, group channels by sampling rate, one `write_bids_physio` per group named `f"{stem_prefix}_recording-{label}_physio"`; with several rates the label gets an alphanumeric rate suffix (e.g. `ecg256hz`). Validates the whole file before creating any output.

- [ ] **Step 1: Failing tests:** `test_target_folder_no_task_is_physio`; `test_target_folder_task_needs_destination` (`pytest.raises(ValueError, match="beh, func, eeg")` for `None` and for `"anat"`); `test_target_folder_task_with_destination`; `test_write_bids_physio_files` (two synthetic channels, assert tsv.gz has no header and shape `(n, 2)` after `gzip`+`np.loadtxt`, sidecar `Columns == ["ecg","resp"]`, `SamplingFrequency == 256.0`, `StartTime == 0.0`); `test_read_edf_roundtrip` (test builds a minimal EDF by hand with `struct` — 2 channels, int16, known digital/physical ranges — and asserts physical values, labels, rates); `test_read_edf_rejects_truncated` (`ValueError`, no output files); `test_edf_to_bids_works_without_pyedflib` (`sys.modules["pyedflib"] = None`, Review Focus 4); `test_edf_to_bids_groups_by_rate` (two-rate hand-built EDF → two recording labels).
- [ ] **Step 2:** Run `pytest tests/test_physio_bids.py -q`; expect FAIL/ImportError.
- [ ] **Step 3:** Implement both modules (numpy `savetxt` into `gzip.open(..., "wt")`, `json.dump`). No new dependency.
- [ ] **Step 4:** Run the file; expect PASS with no skips.
- [ ] **Step 5:** Commit `feat(physio): destination helper and BIDS physio writer`.

### Task 4: Batch converter and `physio batch-convert`

**Files:**
- Modify: `app/helpers/physio/convert_varioport.py` (the pyedflib block ~1143–1160 and the two `f_edf.close()` sites ~1275, ~1349; sidecar write near the end)
- Modify: `src/batch_convert.py` (`BIDS_FILENAME_PATTERN` line 36, `_build_physio_base_name` 362, `convert_physio_file` 876, `batch_convert_folder` 1266, `ConvertedFile`), `app/src/cli/parser.py` (~970–995), `app/src/cli/commands/convert.py:624`
- Test: `tests/test_batch_convert_physio_destination.py` (new); extend `tests/test_batch_convert_dry_run.py`

**Interfaces:**
- Consumes: `physio_target_folder`, `edf_to_bids_physio` (Task 3).
- Produces: `convert_varioport(..., bids_base: str | None = None)` — when set, `output_path`/`sidecar_path` are ignored, pyedflib is never imported, and the signals are written as `<bids_base>.tsv.gz` + flat `<bids_base>.json` via a module-private `_BidsCollector` that offers `setSignalHeaders(headers)`, `writeAnnotation(onset, duration, text)` (ignored: trigger events belong in `_events.tsv`, out of scope), `writeSamples(signals)` and `close()` (calls `write_bids_physio`); `AverageHeartRateBPM` and `TaskName` go into the BIDS sidecar via `extra_meta`; the PRISM nested sidecar is not written in this mode. Default behaviour (`bids_base=None`) is byte-for-byte unchanged.
- Produces: `parse_bids_filename` returns `task=None` when absent; `ConvertedFile.target_folder: str = "physio"`; `convert_physio_file(..., destination: str | None = None)`; `batch_convert_folder(..., physio_destination: str | None = None)`; CLI `physio batch-convert --destination {beh,func,eeg}`.

- [ ] **Step 1: Failing tests** (task-bound `.edf` sources use the hand-built EDF helper from `tests/test_physio_bids.py` (move it to `tests/conftest.py` or a shared helper module); task-bound `.raw` is covered by `test_bids_collector_writes_flat_sidecar` calling `_BidsCollector` directly plus, if an existing Varioport fixture exists in `tests/`, one end-to-end `convert_varioport(..., bids_base=...)` run with `sys.modules["pyedflib"] = None`; the no-task EDF copy path needs no pyedflib): `test_parse_without_task` (`sub-01_ses-pre_recording-ecg.edf` → `task is None`); `test_task_free_edf_lands_in_physio_unchanged` (output `sub-01/ses-pre/physio/sub-01_ses-pre_recording-ecg_physio.edf` is byte-identical to source, `.json` exists); `test_task_bound_without_destination_raises_before_writing` (mixed folder, `ValueError`, `list(out.rglob("*")) == []`; Review Focus 1); `test_task_bound_edf_goes_to_destination_as_tsv_gz` (`destination="beh"` → `sub-01/ses-pre/beh/sub-01_ses-pre_task-stroop_recording-ecg_physio.tsv.gz` and `.json`, no `.edf` anywhere under `beh/`); `test_dry_run_task_bound_writes_nothing` (Review Focus 5); `test_non_physio_file_without_task_is_skipped_with_message` (eyetracking `.edf` without task → in `result.skipped`); `test_session_label_not_normalized` (`ses-1` stays `ses-1`); CLI: `test_batch_convert_cli_requires_destination_for_task_files` (exit code 2, message lists the offending files).
- [ ] **Step 2:** Run the new file; expect FAIL.
- [ ] **Step 3:** Implement: `task` group optional in the regex; `_build_physio_base_name(sub, ses, task, recording_label)` skips a falsy task; `convert_physio_file` computes `folder = physio_target_folder(task, destination)`; `folder == "physio"` keeps today's code path; otherwise `.raw/.vpd` go through `convert_varioport(..., bids_base=...)` and `.edf` through `edf_to_bids_physio(...)`, both into the destination folder, and set `target_folder`. `batch_convert_folder` pre-scans physio-bound files and raises `ValueError` listing task-bound ones when `physio_destination` is falsy, before creating anything; files without task that are not physio get a `skipped` entry. `cmd_physio_batch_convert` passes `args.destination`, catches `ValueError` → stderr + `sys.exit(2)`.
- [ ] **Step 4:** Run new tests plus `tests/test_batch_convert_*.py tests/test_convert_physio_cli.py -q`; expect PASS.
- [ ] **Step 5:** Commit `feat(physio): batch convert supports task-free physio and task-bound BIDS output`.

### Task 5: `convert physio` (Varioport CLI) and single-file API

**Files:**
- Modify: `app/src/cli/commands/convert.py` (`_run_varioport_conversion` gains a `bids_base` pass-through)
- Modify: `app/src/cli/parser.py:49-52`, `app/src/cli/commands/convert.py:108-235`, `app/src/web/blueprints/conversion_physio_handlers.py:533-600`
- Test: extend `tests/test_convert_physio_cli.py`

**Interfaces:**
- Consumes: `physio_target_folder`, `convert_varioport(..., bids_base=...)` (Task 4).
- Produces: `convert physio --task` has no default; new `--destination {beh,func,eeg}`; no `--task` → output in `physio/` named without `task-`; with `--task` and no `--destination` → error exit 2, nothing written; with both → tsv.gz + sidecar in the destination folder.

- [ ] **Step 1: Failing tests:** `test_no_task_writes_physio_folder_without_task_entity`; `test_task_without_destination_exits_2_and_writes_nothing`; `test_task_with_destination_writes_bids_files` (stub `convert_varioport` with a fake that honors `bids_base` via `_BidsCollector`; pyedflib absent). Existing assertions that expect `task-rest` by default must be updated.
- [ ] **Step 2:** Run `pytest tests/test_convert_physio_cli.py -q`; expect FAIL on the new ones.
- [ ] **Step 3:** Implement via `physio_target_folder`; `out_base` omits `task-` when no task; the root-level `task-<t>_physio.json` the command writes today is dropped (task-free output gets a per-file sidecar next to the EDF; task-bound sidecars come from `edf_to_bids_physio`). `/api/physio-convert` drops the `"rest"` default (blank task → `task_name=""`).
- [ ] **Step 4:** Run the file; expect PASS. Commit `feat(physio): convert physio CLI supports no task and --destination`.

### Task 6: Renamer / organizer

**Files:**
- Modify: `src/physio_renamer.py:320-337`, `app/src/cli/commands/file_management.py:203-240` and its parser entry (modality choices)
- Test: extend `tests/test_physio_renamer.py`, `tests/test_cli_file_management_rename_physio.py`

**Interfaces:**
- Produces: `compute_organized_relative_path(..., modality="physio")` raises `ValueError` (message names `beh`, `func`, `eeg`) when the parsed filename has `task-`; with `modality` in `beh|func|eeg` it organizes into that folder as before; `plan_rename` already turns the exception into `success: False`.

- [ ] **Step 1: Failing tests:** `test_organize_physio_with_task_fails_with_hint`; `test_organize_task_free_physio_ok` (`sub-01_ses-pre_recording-ecg_physio.edf` → `sub-01/ses-pre/physio/...`); `test_organize_into_beh_ok`; CLI: `--modality beh` accepted.
- [ ] **Step 2:** Run both files; expect FAIL.
- [ ] **Step 3:** Implement the check inside `compute_organized_relative_path`; extend CLI `--modality` choices.
- [ ] **Step 4:** Run both files; expect PASS. Commit `feat(file-management): physio organizer rejects task in physio/, offers beh/func/eeg`.

### Task 7: GUI wiring

**Files:**
- Modify: `app/templates/converter_physio.html` (add "Destination for files with a task" select near `physioBatchDeviceType`, ~line 108), the JS that builds the batch form data (find with `grep -rn "physioBatchDeviceType" app/static/js`), `app/src/web/blueprints/conversion_physio_handlers.py` (`_run_batch_job` ~99–280, `api_batch_convert_start` ~286, `api_batch_convert` ~607 and ~880, session registration ~241 and ~1012), `app/templates/file_management.html` (~347 modality options; example texts at ~147, 231, 405, 415, 748 that show `task-rest_physio` inside `physio/`)
- Test: `tests/test_conversion_physio_handlers_destination.py` (new)

**Interfaces:**
- Consumes: `batch_convert_folder(..., physio_destination=...)`, `ConvertedFile.target_folder`.
- Produces: form field `physio_destination`; handlers return HTTP 400 with the `ValueError` text when the backend raises it; sessions are registered per `(session, cf.target_folder)` with the task list possibly empty (drop the `and cf.task` condition).

- [ ] **Step 1: Failing tests** with the Flask test client (follow an existing handler test for fixtures): `test_batch_start_without_destination_for_task_files_is_400`; `test_batch_start_passes_destination` (monkeypatch `batch_convert_folder`, assert kwarg); `test_session_registered_under_target_folder` (monkeypatch `register_session_in_project`, assert called with `"beh"` and with `[]` tasks for a task-free `physio` file; confirms Review-Focus-adjacent behaviour that task-free sessions register).
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement: read `physio_destination` from the form/JSON in both batch endpoints and `config`; pass through; update registration; add the select (options: blank, `beh`, `func`, `eeg`, help text "Needed only for files whose name contains task-…"); add `beh/func/eeg` to the renamer modality select; fix the example strings.
- [ ] **Step 4:** Run the new file and `pytest tests -q -k "conversion_physio or physio_handlers"`; expect PASS. If a Playwright test in `tests/e2e` covers the physio page, run it (`pytest tests/e2e -k physio`) and report if it cannot run locally.
- [ ] **Step 5:** Commit `feat(gui): destination select for task-bound physio conversion`.

### Task 8: Docs, changelog, full verification

**Files:**
- Modify: `docs/specs/entities.md`, `docs/studio/converter_physio.md`, `docs/TUTORIAL_FILE_MANAGEMENT.md`, `docs/SPECIFICATIONS.md`, `docs/studio/index.md`, `docs/INTRODUCTION.md`, `docs/index.rst`, `CHANGELOG.md`

- [ ] **Step 1:** Update each doc where it mentions `physiological`, an `events/` folder, or task-bound files in `physio/`; document the rule (task-free → `physio/` EDF; task → `beh|func|eeg` as BIDS tsv.gz) and the new `--destination` option. CHANGELOG entry marks the retired folders as a breaking change with the fix hints.
- [ ] **Step 2:** Run `python tests/verify_repo.py --no-fix` (includes dual-tree-drift and modality-docs checks); expect no new failures. Fix generated modality docs if the check says so (`events` is now `folder: false`).
- [ ] **Step 3:** One full run of the suite (cross-cutting change): `pytest -q`. Report every failure by name, including ones not caused by this branch.
- [ ] **Step 4:** Commit `docs: physio without task, retired events/ and physiological/`.
- [ ] **Step 5:** Invoke `superpowers:finishing-a-development-branch`; run `/ponytail:ponytail-audit` before the merge step.
