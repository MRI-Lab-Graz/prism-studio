# Handoff: code maps for all importers (2026-11-26)

Branch `feat/code-maps`. Not merged, no pull request.

```bash
git fetch origin && git switch feat/code-maps
```

Plan: `docs/superpowers/plans/2026-11-26-code-maps-all-importers.md` (executed in one session,
`superpowers:executing-plans`, TDD). Spec: `docs/superpowers/specs/2026-11-26-code-maps-design.md`.
**Task 5 (participants) is left out for now, on request.**

## State

| Task | State |
|---|---|
| 1 shared `ProjectCodeMaps` in `src/code_maps.py` | done (94 tests passed) |
| 2 biometrics | done (120 passed) |
| 3 environment | done (163 passed) |
| 4 biosample | done (173 passed) |
| 5 participants | **skipped** |
| 6 raw files (`src/batch_convert.py`) | **only the failing tests**: `tests/test_raw_file_code_maps.py` (11 fail), WIP commit |
| 7 importer list, docs | open |

The full test suite has not been run. No branch review, ponytail audit, code review or security review yet.

## Task 6: what to build

Found while reading, beyond the plan:

- **Same staging bug as biometrics.** CLI `--project` and Studio convert into a temp folder, so
  `resolve_import_session(output_folder, ...)` never sees the project. Add
  `project_root=None` (default: `output_folder`) to `batch_convert_folder`; CLI passes the `--project`
  path; the three Studio calls in `conversion_physio_handlers.py` pass the active project, also on dry run
  (`_requested_project_path() or session.get("current_project_path")`; the async job has `config["project_path"]`).
- **The typed code leaks through the source file name** (sidecar `SourceFile`, logs, warnings, reports).
  Intended fix: a helper that runs before anything is converted, copies each mapped file to
  `<tmp>/<n>/<name with the mapped sub->` and converts that copy.
- **Two codes for one participant would overwrite silently** (`result.conflicts` is never filled):
  raise `CodeMapError` naming the new file name.
- Resolve all files first (`resolve_all(..., keep_targets=True)`), collect every unknown label, raise
  one `UnknownCodeError`.
- Maps of a physio file are `physio_*`, also when it is written to `beh/`, `func/` or `eeg/` (the spec says
  the file's modality; the plan's "same name as the output folder" would miss `physio_code_map.tsv`).
  Other files: the selected modality, or `extra` under `all`.
- `--subject-rewrite-mode last3` would shorten a mapped participant: mark `ConvertedFile.mapped` and skip the
  rewrite for those in `save_physio_batch_to_project`.
- `cmd_physio_batch_convert` and the two Studio `except PhysioDestinationError` blocks also catch `CodeMapError`
  (CLI exit 2, Studio 400).

## Task 7

Move biometrics, environment, biosample and batch_convert to `USES_CODE_MAPS` in
`tests/test_importers_use_code_maps.py` (extend its regex with `ProjectCodeMaps`; that test may fail until
then). `participants_backend.py` stays in `KNOWN_GAPS`. `project_registration.py` goes to an exempt list
("reads no participant IDs"). Update `docs/CODE_MAPS.md` (per-modality table, raw-file rule; say participants
import does not use maps yet; no task maps for biosample or environment).

## Decisions made along the way (check these)

- `ProjectCodeMaps.open` takes an optional `known_sessions` override (survey passes hand-named sessions).
- Biometrics converter has a new `project_root` argument. **Behaviour change:** staged imports now follow the
  project's session rule (before, a one-timepoint project got `ses-pre` instead of `ses-1`); multiple-timepoint
  projects stop on unmapped sessions. Needs a release note.
- Environment requires a participant column, so a typed participant only fills empty cells.
- Biosample has no task scope: the panel is a `biosample-` entity. A task map is only reported.
- No extra CLI/Studio parity cases for environment and biosample (Studio calls the same function unchanged).

## Open points, not changed

- Studio's `log_file_head` echoes the first 4 uploaded lines (including typed codes) in the survey and
  biometrics logs.
- Release notes: an existing `code/<modality>_code_map.tsv` is now applied without being asked.

## Setup on the other PC

Tests: `PRISM_SKIP_VENV_CHECK=1 <repo>/.venv/bin/python -m pytest -q <files>`.
Code maps are never in git, so real maps have to be copied by hand. Claude's memory and the untracked
files in the main checkout (`docs/superpowers/plans/2026-11-23-specification-identifiers-fingerprints.md`)
stay on the old PC.
