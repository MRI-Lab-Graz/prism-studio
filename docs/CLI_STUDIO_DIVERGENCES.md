---
orphan: true
---

# Where Studio and the CLI still differ

**These are bugs.** The rule (root `CLAUDE.md`): the CLI executes, Studio only triggers. Each entry is to be removed by
making Studio call the same backend function as the command, with the same options and defaults. Found by reading the code
and comparing options; not exhaustive. Add what you find, delete what you fix, and prove each fix with a test in
`tests/test_cli_studio_parity.py`.

## How this list is kept honest

`scripts/check_cli_studio_parity.py` lists every backend function Studio imports and no CLI command imports
(`python scripts/check_cli_studio_parity.py`). Its reviewed baseline, `scripts/cli_studio_baseline.json`, may only
shrink; `tests/test_cli_studio_guard.py` fails CI when Studio starts using backend code the CLI does not. Each entry in
the baseline is a divergence to review: fix it (the CLI runs it too) and delete the entry.

## `survey convert` (done)

Same options, same defaults, one code path: the command builds Studio's `SurveyWorkflowStageOptions` and runs Studio's
`SurveyWorkflowStageService` with the backend runner `run_survey_with_template_sources`. `tests/test_survey_convert_options_parity.py`
fails when a Studio option has no CLI flag or the defaults differ.

## Logic that lives in Studio only (no command runs it)

- `app/src/web/blueprints/conversion_survey_official_template_helpers.py` - checking which official templates match an
  uploaded file (`infer_tasks_against_official_templates`) and resolving the official library on its own
  (`resolve_official_survey_dir`). No CLI command.
- `app/src/web/blueprints/conversion_survey_handlers.py` - "detect version contexts" (which template versions a file
  needs) builds its own merged library. No CLI command.
## Review results (first pass)

Method: for each Studio endpoint with an obvious CLI command, read the form fields the route takes and the flags the command
has. The automatic field extraction misses fields read through helpers (it missed `sessions_from_date`), so every finding
below was confirmed by reading the code. Fixed items have a test; open ones are listed with what Studio does.

### The "save to project" step - survey done, the other conversions open
After a conversion Studio stages the files, copies them into the project with a DataLad-aware copy and commit, optionally
archives the source file in `sourcedata/`, registers the template versions in `project.json` and syncs the recipe offsets.
**Done for surveys**: `src/conversion_to_project.py::save_conversion_to_project` does all of it; Studio's three survey routes and
`survey convert` (when the output is the project) call it, and `tests/test_survey_convert_saves_into_the_project.py` runs Studio's
real Convert route against the command on identical projects and compares every file. Open: biometrics, physio and
environment routes still carry their own copy of the tail (and register sessions through `src/project_registration.py`);
their commands write straight into `--output`.

### Physio
- **Batch convert: done.** `src/conversion_to_project.py::save_physio_batch_to_project` maps every file to its destination
  (`dest_root`, flat, subject rewrite), copies with the DataLad-aware copy, registers the sessions and warns about new subject
  folders. Studio's async job, its synchronous batch (folder and upload mode) and `physio batch-convert --project` call it;
  `tests/test_physio_batch_saves_into_the_project.py` runs Studio's real route against the command. It also removed a
  difference *inside* Studio: the synchronous route never registered sessions and never wrote `dataset_description.json`.
- **Single-file convert: done.** The Varioport call with its Type-7 retry exists once (`src/physio_varioport.py`); `convert physio`
  and Studio's Physio converter use it.
- **Renamer, the rule: done.** `src/physio_renamer.py::rename_one` (name, filename check, BIDS organize) is the one rename rule;
  `plan_rename` (the command) and Studio's three inline copies in `api_physio_rename` call it. `tests/test_physio_rename_parity.py`
  runs Studio's dry-run against the command. The copies had drifted both ways: Studio lacked the organize refusals (no `events/`
  folder, no task-bound physio in `physio/`, no raw EDF in beh/func/eeg) and the command lacked the filename check.
  Decision (2026-10-30): both refuse.
- **Renamer, save to project: done** (`save_renamed_to_project`; `rename-physio --apply --project`). Before: open. Studio's route copies renamed files into the project (`dest_root`, `flat_structure`,
  `subject_rewrite_mode`, subject-folder warnings, its own second copy of the organize logic); `file-management rename-physio`
  only writes to `--output`.

### Environment - already compliant
`src/environment_conversion.py::perform_environment_conversion` is the one engine; `environment convert` calls it and Studio's
route runs the command in a subprocess.

### Participants
- Preview: Studio's route composes the column selection itself (filter relevant columns, `excluded_columns`, extra columns)
  from `src.participant_columns` helpers; the command composes it its own way. The command has no `--excluded-columns` or
  `--extra-columns`. Fix: one backend function for the column selection.

### Export - done: the CLI drives it, Studio triggers it
Every export route of Studio's page runs a backend function that a command runs too: `export project` (zip, with the validation
gate), `export folder`, `export git-lfs`, `export annex-availability`, `export structure`, `export deface-report|deface-preflight|deface`
(the run defaces a copy, never the project), `export anc`, `export openminds` and `openminds-tasks`, and `template-export`
(which now validates first and names its zip like Studio). The code is `src/export_options.py`, `src/export_defacing.py`,
`src/export_openminds.py` and `src/project_export.py` (moved out of Studio's tree). Tests run each command against Studio's
real route. Still open: the async job's status/download/cancel routes are job plumbing in the GUI (the work they run is the
shared function), and the pre-export validation reaches two helpers in Studio's validation module (see `ponytail:` in
`src/export_options.py`).

### Recipe builder
Studio's analysis endpoints (`/api/recipe-builder/surveys|items|load`) decide what a new recipe contains (item extraction, scale
range detection from a template). The CLI can only save a finished recipe (`recipes save`); nothing drafts one from a template.
Needs `recipes draft` running `src.recipe_builder`.

### Survey template matching and the LimeSurvey tools
`survey import-limesurvey` has `--split`, `--select`, `--use-library`, `--project`; Studio's `limesurvey-to-prism` and
`limesurvey-save-to-project` routes call `converters.limesurvey` parsers and `survey_templates.match_*` directly. Probably the
same code paths, not confirmed: read both and add a parity test as for `survey convert`.

### Biometrics - done
`biometrics convert` resolves the library from the project, matches participant IDs against the project's `participants.tsv`,
and saves into the project with the shared function (template copies included); it has `--project` and `--dry-run`.
`tests/test_biometrics_convert_saves_into_the_project.py` runs Studio's real route against the command.

### Not yet read
Environment and file-management routes (their form fields were not extractable by the automatic pass).

## Review queue: the Studio-only backend calls, by area

`scripts/cli_studio_baseline.json` lists 146 backend functions that Studio imports and no CLI command does. Grouped by where
Studio uses them (a first sort by file, not yet a line-by-line read of each):

**Real workflows to review first** (each: does a CLI command run the same code, or does the route carry its own?)

| Area | Studio code | Check |
|---|---|---|
| Export (defacing, anonymising, phenotype export) | `export_project`, `projects_export_blueprint`; `src.mri_json_scrubber` (7), `anonymizer`, `phenotype_export`, `survey_dates`, `project_export_helpers`, `git_exclude` | `publish`, `template-export` and `anonymize` exist; is there a command for the defacing export? |
| Physio conversion | `conversion_physio_handlers`; `src.physio_renamer` (9) | `convert physio`, `physio batch-convert`, `file-management rename-physio`: same helpers? |
| Recipe builder | `tools_recipe_builder_handlers`; `src.recipe_builder` (8) | `recipes save` exists; no command for the template analysis (scale ranges, item descriptions) |
| Participants columns | participants blueprints; `src.participant_columns` (7), `participants_levels`, `participants_backend` | `participants preview`/`neurobagel-schema`/`merge`: same column detection? |
| Survey template matching | `conversion_survey_handlers`, `tools_library_handlers`; `converters.survey_templates` (4), `converters.survey` (5) | matching a file against the library, version overrides, recipe offset sync: command? |
| LimeSurvey tools | `tools_generation_handlers`, `tools_limesurvey_handlers`; `converters.limesurvey` (3), `excel_to_survey` | `survey import-limesurvey`, `export-lss`: same parsers? |
| Template check against the official library | `conversion_survey_official_template_helpers` | no command |
| Version-context detection | `conversion_survey_handlers` | no command |

**Only project setup is exempt**: creating a project and its study metadata (including the DOI and ORCID lookups that fill the
metadata form). Everything else in this baseline is a divergence to fix, not "infrastructure":
- DataLad server publish and sync, remote browse and rsync, project structure and the sessions/participants pages, project
  registration, session logging.
- Pure UI state needs no command (icons, which card is open, the dedicated terminal window, the version check): confirm each
  and list it in the baseline with that reason.

**Probably the same function under another name** (check, then fix the guard or the import): `src.issues` (error texts for the
results page), `spec_overlay` (the Contribute page lists items; `spec local list` exists), `converters.file_reader` and
`id_detection` (helpers).

## Two implementations of the same thing

- **Picking one language out of a multilingual template**: `src/survey_localize.py` (the converters) and
  `library_i18n.compile_survey_template` (`library i18n build`) are separate implementations.
- **Choosing a template library**: `resolve_survey_library` (a single folder, for the editor and validation) and
  `template_tiers` (the per-template merge for conversions) state the project, personal, global order twice.

## Fixed (keep the tests green)

- Settings: `prism_tools.py settings show|set`; the Settings page's four routes and the command run `src/settings_update.py`.
  The command has one flag per setting, generated from the same table the page uses.

- Saving a template: `library template-save` and the editor's Save run `src/template_save.py`. The command used to skip the
  task-name check for library templates that the editor always made.
- `survey convert`: Studio's options and service run in the CLI; same flags, same defaults.

- Library choice, merge order and copying used templates into the project: one function for both
  (`src/survey_template_sources.py`).
- Dry-run: both leave the used templates in the project and write no data.
- Language maps: the converter picks the language for both; the CLI no longer compiles templates itself.
- Validation never rewrites `participants.tsv`.
