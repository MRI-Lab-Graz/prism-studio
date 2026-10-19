# Physio without task, no `events/` folder, no `physiological` alias

Date: 2026-10-19 · Branch: `feat/physio-no-task-drop-events-folder`

## Why

PRISM sticks to BIDS wherever BIDS has a definition. In BIDS, `_physio` and
`_events` files are bound to a task and live in that task's datatype folder:

- fMRI task with respiration: `func/sub-01_task-x_recording-resp_physio.tsv.gz`
- PC lab task (PsychoPy etc.): `beh/sub-01_task-x_events.tsv`, `..._physio.tsv.gz`
- EEG task: `eeg/...`

BIDS has no place for physiology recorded **without** a task (30 min ECG
before the MRI, sleep recording the night before). That gap is the only
reason PRISM's own `physio/` folder exists.

## Goals

1. `physio/` holds task-free recordings only. A `task-` entity in a `physio/`
   filename is an **ERROR** whose message names where the file belongs
   (`beh/`, `func/` or `eeg/`, next to that task).
2. `events` stops being a folder modality. A `sub-*/[ses-*/]events/` folder is
   flagged (ERROR, hint: move `_events.tsv` next to its task in `func/`/`beh/`/`eeg/`).
   PRISM's events-schema checks on `*_events.tsv` inside `func/`/`beh/` stay as they are.
3. `physiological` alias is dropped entirely. A `physiological/` folder is
   flagged (ERROR, hint: rename to `physio/`). All hand-written
   `"physiological"` checks are deleted.
4. Every physio writer supports both cases:
   - **no task** → `sub-X/[ses-Y/]physio/sub-X[_ses-Y]_recording-<r>_physio.<ext>`
   - **task given** → the user **must** state the destination (`beh`, `func`
     or `eeg`); no default. Output: `sub-X/[ses-Y/]<dest>/sub-X[_ses-Y]_task-<t>_recording-<r>_physio.<ext>`.
     Task given without destination → error, nothing written.
5. Same options on CLI and GUI (GUI/CLI parity rule).

## Non-goals

- No new modality for sleep. Raw night signals → `physio/` (e.g.
  `recording-actigraphy`, already allowed by `allowOther`). Nightly summary
  values → `biometrics/`.
- No automatic migration/fixer that moves existing files. The validator
  message says where they go; a mover can come later if asked for.
- No generic "unknown folder" warning; only the two retired names are flagged.

## Anti-goals

- No silent default destination for task-bound physio.
- No second copy of the destination logic in GUI/JS — one backend helper.

## Constraints

- Shipped as one merge (validator + converters), so no project goes red
  without a converter that can produce valid output.
- Session/subject labels are never normalized.
- TDD: failing test first for each change.

## How (decided)

**Rules file** `app/schemas/stable/entities.schema.json`:
- delete `"aliases": {"physiological": "physio"}`;
- delete the `events` modality entry (no folder grammar needed; `_events.tsv`
  inside `func/`/`beh/` is still routed to the `events` sidecar schema by
  `runner._effective_modality_for_file`, which keys on the suffix, not on the
  rules file — builder must confirm nothing else reads `modalities["events"]`);
- give `physio` `"allowedEntities": ["acq", "run", "recording"]` so the existing
  `check_entities` path in `validator.validate_filename` rejects `task-`.
  Validator adds the destination hint for the `task` case.

**Validator / runner** (`app/src/validator.py`, `app/src/runner.py`):
- in `_validate_subject` / `_validate_session`, a directory named `events` or
  `physiological` produces the ERROR + hint above (one small dict
  `RETIRED_FOLDERS = {name: hint}` in runner).
- remove `"physiological"` from validator.py, runner.py, stats.py, issues.py,
  bids_validator.py, web/upload.py; remove `"events"` where it is listed as a
  folder modality (issues.py, bids_validator.py, upload.py, modality_versions
  special case) — keep it where it means the `_events.tsv` suffix/schema.

**One destination helper** in `src/batch_convert.py` (backend, reused by all
writers):

```python
PHYSIO_TASK_DESTINATIONS = ("beh", "func", "eeg")

def physio_target_folder(task: str | None, destination: str | None) -> str:
    """'physio' when there is no task; otherwise the stated BIDS datatype.
    Raises ValueError when a task is given without a valid destination."""
```

**Writers:**
1. `src/batch_convert.py` — `BIDS_FILENAME_PATTERN` makes `task-` optional;
   `convert_physio_file` / `batch_convert_folder` take `physio_destination`;
   folder from the helper; `_build_physio_base_name` omits task when none.
   Eyetracking/generic files without `task-` are skipped with a clear message
   (unchanged behaviour for them).
2. CLI `prism_tools physio batch-convert` gets `--destination {beh,func,eeg}`.
3. CLI `prism_tools convert physio` (Varioport): `--task` loses its `rest`
   default (optional), gains `--destination`; folder from the helper.
4. `src/physio_renamer.compute_organized_relative_path` (file-management
   rename/organize, CLI `file-management rename-physio`): when modality is
   `physio` and the filename has `task-`, the result is marked failed with the
   destination hint instead of being organized into `physio/`. User already
   picks the modality there; add `beh`/`func`/`eeg` to the options if missing.
5. GUI: converter_physio batch form gets a "Destination for files with a
   task" select; the file-management renamer offers `beh`/`func`/`eeg` next
   to `physio`; handlers only pass the values through. Example texts that show
   `task-rest_physio` inside `physio/` are updated. Single-file
   `/api/physio-convert` (ZIP download) just drops the `rest` default.

**Docs:** update `docs/specs/entities.md`, `docs/studio/converter_physio.md`,
`docs/TUTORIAL_FILE_MANAGEMENT.md`, `docs/SPECIFICATIONS.md`,
`docs/studio/index.md`, `docs/INTRODUCTION.md`, `docs/index.rst` where they
mention `physiological`, an `events/` folder, or task-bound files in `physio/`.

## Settled after review (my calls, check while reading)

- **Batch task source:** the task keeps coming from each source filename, as
  today. The batch form gets **no** task field, only "Destination for files
  with a task" (CLI: `physio batch-convert --destination`). Parity holds.
- **Batch with task-bound files and no destination:** the whole job fails
  before writing anything, listing the task-bound files. No partial output.
- **`events` version pinning:** keep the `events` entry in the rules file
  (so `modality_names()`, `SchemaVersions.events` pins and the
  `modality-version` command keep working) but mark it `"folder": false`.
  Folder discovery in runner (`MODALITY_PATTERNS`-based `item in ...` checks)
  and `project_modalities` skip non-folder entries; `present_modalities`
  keeps its suffix-based events detection, minus the `events/` folder glob.
  This replaces "delete the `events` modality entry" above.
- **project.json session registration** after batch conversion: register
  each converted file under its actual folder (`physio`, `beh`, `func`,
  `eeg`). Task-free files register with an empty task list; builder checks
  `register_session_in_project` and the session map accept that, and adds a
  test.

## Output format (decided by the user)

- **`physio/` (no task, PRISM):** EDF + PRISM sidecar, unchanged. The EDF
  format is not touched.
- **`beh/`, `func/`, `eeg/` (task given, BIDS):** BIDS format only:
  `sub-X[_ses-Y]_task-<t>[_recording-<r>]_physio.tsv.gz` (no header row) plus
  a flat BIDS sidecar `..._physio.json` with `SamplingFrequency`, `StartTime`,
  `Columns` (and the usual optional fields). No EDF and no PRISM-style nested
  sidecar in these folders. PRISM does not validate these files; the BIDS
  validator does.
- Source `.raw`/`.vpd` is first decoded by the existing Varioport converter,
  then its signal is written either as EDF (no task) or as tsv.gz (task).
  One conversion path, two writers.
- BIDS requires one sampling frequency per physio file. If the source has
  channels at different rates, the builder writes one file per rate
  (distinguished by `recording-<label>`); builder's call how to group.
- The `.bidsignore` question is moot: nothing PRISM-only lands in BIDS folders.

## Left to the builder

- Exact wording of the hint messages (must name the destination folders).
- Whether `ConvertedFile.task` becomes `str | None` or `""`.
- Order of tasks in the plan; test file layout (one new
  `tests/test_physio_no_task.py` plus additions to existing files is fine).
