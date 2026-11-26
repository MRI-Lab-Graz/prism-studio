# Project code maps: design

Date: 2026-11-26. Status: draft, waiting for approval.

## Intent

People type their own code into a survey (initials, birth month, ...). The project's participant
numbers (`sub-004`) live in a separate table. Today that table is a file the user passes by hand with
`--id-map` (Studio: the "ID map" upload). Nothing records which table a project uses, and one table
cannot express codes that differ between tasks or sessions.

A project should hold its code maps, the importers should find them by name, and the user should be
able to narrow a map to a task or a session.

## Goals

- One general map per modality: `code/<modality>_code_map.tsv` (for example `code/survey_code_map.tsv`).
- Narrower maps with BIDS-style names, applying only to what the name says.
- The same files and messages from the CLI and Studio.
- A dedicated Read the Docs page.

## Non-goals

- Renaming data that was already imported.
- Guessing or fuzzy-matching codes. Typos stay explicit rows in a map.
- A map shared by all modalities.
- `run-` or other entities in the file name.

## File names

| File in `code/` | Applies to |
|---|---|
| `survey_code_map.tsv` | all survey imports |
| `survey_task-ads_code_map.tsv` | task `ads` only |
| `survey_ses-3_code_map.tsv` | every task in session 3 |
| `survey_task-ads_ses-3_code_map.tsv` | task `ads` in session 3 only |

`ses-<label>` is the label written to the dataset (after the project's session rule), compared as an
exact string. `task-<label>` is the task label written to the dataset. Order is `task`, then `ses`.

## File format

Tab-separated, header `code<TAB>participant_id`. The same reading rules as `--id-map` today.
Codes match without regard to case and surrounding spaces. Several codes may point to one
participant (a person who typed two spellings).

## Lookup

For one code in one task and session, the first file that lists the code wins:

1. `task-X_ses-Y`
2. `task-X` and `ses-Y` (equally specific: if both list the code with different participants, stop
   and name both files)
3. the general map

A code that no applicable file lists stops the import, as `--id-map` does today. A narrow file only
needs the codes that differ.

## One row, one participant

A response row can hold several tasks (in the Dance and Brain project: six questionnaires, one typed
code). If the tasks of one row resolve to different participants, the import stops and names the
code, the tasks, the participants and the files. Nothing is written.

The check covers every task whose columns are in the file, including tasks left out with `--survey`.
Otherwise importing one task at a time would get around it.

Consequence: a task map can only give a different result when that task comes in its own file.

## Rules that stop the import

- The disagreements above (two files, or two tasks of one row).
- The same code twice in one file with different participants. (`--id-map` currently keeps the last
  one silently. This also gets fixed.)
- A file name that starts with the modality and ends in `_code_map.tsv` but does not parse
  (`survey_taks-ads_code_map.tsv`).
- A session-scoped file lists a code found in the data, but the import has no session for that row,
  or the session is only numbered from response dates (`--duplicate-handling sessions`). The number
  depends on knowing the participant first, so the session must come from `--session` or a column.

A `task-` file naming a task that this import does not contain is normal. One naming a task the
project has no template for is reported as a warning.

## What is reported

Preview and import both report each map file used and how many codes it resolved. Same text in CLI
and Studio.

## Interaction with what exists

- `--id-map FILE` given: only that file is used, as today. Project maps that were ignored are
  reported.
- No `--id-map` and no project maps: behaviour unchanged.
- **Behaviour change:** a project that already has `code/survey_code_map.tsv` will have it applied
  without being asked. A value in the data that the map does not list then stops the import. The
  release notes must say so.

## Approaches

1. **One resolver in `src/`, files found by name (chosen).** Maps live with the project and the name
   shows the scope. Cost: precedence rules that must be documented.
2. **One table with `code, participant_id, task, session` columns.** One file to audit and no name
   parsing. Rejected: BIDS-style names were requested.
3. **Repeatable `--id-map` flags with a scope.** No discovery and no behaviour change. Rejected: the
   project would not record which maps were used.

## Build notes

- New module `src/code_maps.py`: discover, parse names, load, resolve. Takes the modality as an
  argument and knows no modality list of its own.
- Survey: `app/src/converters/survey.py` applies the ID map before sessions are resolved and before
  columns are mapped to tasks (around `_apply_subject_id_mapping`). Scoped resolution needs both, so
  that step has to be split or moved. This is the main risk of the work.
- Column choice: today the ID column is picked by overlap with the map. With project maps, score
  against all codes of all maps.
- `survey import-limesurvey batch` also takes `--id-map` (`src/converters/limesurvey.py`). It uses
  the same resolver or refuses when scoped maps exist.
- Other modalities: every importer that takes participant IDs from data uses the same resolver with
  its own prefix (`biometrics_code_map.tsv`, ...). Follow the pattern of
  `tests/test_importers_use_session_policy.py`: each importer is listed as using it or exempt with a
  reason. Survey ships first; the feature is done when the list has no gaps.
- Studio adds no logic. The upload stays the `--id-map` equivalent.
- Tests: resolver unit tests for each rule above; a survey conversion test for the row disagreement;
  a case in `tests/test_cli_studio_parity.py`.

## Documentation

New page `docs/CODE_MAPS.md` in the Read the Docs toctree: why codes need a map, file names with the
table above, format, lookup order, each stop message and how to fix it, a worked example with
invented codes (never real ones), and the privacy note below. Link it from the survey tutorial and
`CLI_REFERENCE.md`.

## Privacy of the map (decided 2026-11-26)

A code map links self-chosen codes (which can contain initials and birth month) to participant
numbers. It re-identifies pseudonymised data. Project export includes `code/` by default
(`src/project_export.py`, `include_code`).

Code maps are left out of every export and share, whatever the include options say, and the export
reports which files it left out. This covers every `code/*_code_map.tsv`.

They are also kept out of git, like `code/anonymization_map.json`, because a file that was once
committed stays in history. Cost: a colleague who receives the project does not get the maps and
cannot repeat the import. The documentation page says to hand them over separately.

A map that is already tracked by git is not removed from history; the import warns about it.

Limit: this protects the map files only. Other files that hold codes next to participant numbers
(for example a spreadsheet in `sourcedata/`) are not detected. The documentation page says so.

Tests: an export of a project with maps contains none of them, with `include_code` on.
