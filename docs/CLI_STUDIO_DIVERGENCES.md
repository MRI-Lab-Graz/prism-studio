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

### The "save to project" step is Studio-only (all conversions) - the biggest gap
After a conversion Studio stages the files, copies them into the project with a DataLad-aware copy and commit
(`copy_files_into_project`), optionally archives the source file in `sourcedata/`, registers the template versions in
`project.json` (`register_session_in_project`, which lives in the Studio tree: `app/src/web/services/`), and syncs the
recipe offsets (`sync_project_survey_recipe_offsets`). Survey, biometrics, physio and environment conversions all do it in
their routes. The commands write straight into `--output` and do none of it. Fix: one backend function for the tail, called
by the commands and by the routes; move `register_session_in_project` to `src/`. (Not started: needs a decision on DataLad
commits for the CLI.)

### Physio
- `physio batch-convert`: **fixed** `--generate-physio-reports` and `--dataset-name` (the command now also writes
  `dataset_description.json` like Studio). Open: `save_to_project`, `dest_root`, `flat_structure`, `subject_rewrite_mode`
  (the save-to-project step above). Test: `tests/test_physio_batch_options_parity.py` lists the open ones and fails when a new
  Studio option appears.
- Physio renamer: the command calls `plan_rename`; Studio's 449-line route builds its own pipeline from nine helpers of the same
  module and has `dest_root`, `flat_structure`, `subject_rewrite_mode` and the project copy, which the command lacks. Two
  implementations of the rename plan: the route should call `plan_rename`.

### Participants
- Preview: Studio's route composes the column selection itself (filter relevant columns, `excluded_columns`, extra columns)
  from `src.participant_columns` helpers; the command composes it its own way. The command has no `--excluded-columns` or
  `--extra-columns`. Fix: one backend function for the column selection.

### Export - mostly no CLI command at all
`projects_export_blueprint.py` is 1,536 lines with six functions over 80 lines. The CLI has `template-export`, `anonymize` and
`publish`; Studio's other export features have no command: the main project export (zip, folder, structure), the DataLad annex
availability check, Git-LFS export, defacing (preflight, report, run) and the ANC and OpenMinds exports. The helpers are in
`src/` (`mri_json_scrubber`, `anonymizer`, `phenotype_export`, `project_export_helpers`, `git_exclude`); the orchestration (what
is copied, filtered, zipped) is in the blueprint. Each needs a command that runs the same function, and the blueprint reduced to
calling it.

### Recipe builder
Studio's analysis endpoints (`/api/recipe-builder/surveys|items|load`) decide what a new recipe contains (item extraction, scale
range detection from a template). The CLI can only save a finished recipe (`recipes save`); nothing drafts one from a template.
Needs `recipes draft` running `src.recipe_builder`.

### Survey template matching and the LimeSurvey tools
`survey import-limesurvey` has `--split`, `--select`, `--use-library`, `--project`; Studio's `limesurvey-to-prism` and
`limesurvey-save-to-project` routes call `converters.limesurvey` parsers and `survey_templates.match_*` directly. Probably the
same code paths, not confirmed: read both and add a parity test as for `survey convert`.

### Not yet read
Biometrics, environment and file-management routes (their form fields were not extractable by the automatic pass).

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

**Projects pages and Studio infrastructure** (exempt by the rule, or UI only; confirm and move them to a short "UI-only"
list with a reason): project icons, project root/registration/structure/session logging, project-ready gate, settings
(`src.config`), dedicated terminal, remote browse / rsync / DataLad server, DOI and ORCID lookup, version check,
`src.api`, JSON editor blueprint, `cross_platform`, `system_files`, `runtime_dependencies`, `template_info`, `folder_create`.

**Probably the same function under another name** (check, then fix the guard or the import): `src.issues` (error texts for the
results page), `spec_overlay` (the Contribute page lists items; `spec local list` exists), `converters.file_reader` and
`id_detection` (helpers).

## Two implementations of the same thing

- **Picking one language out of a multilingual template**: `src/survey_localize.py` (the converters) and
  `library_i18n.compile_survey_template` (`library i18n build`) are separate implementations.
- **Choosing a template library**: `resolve_survey_library` (a single folder, for the editor and validation) and
  `template_tiers` (the per-template merge for conversions) state the project, personal, global order twice.

## Fixed (keep the tests green)

- Saving a template: `library template-save` and the editor's Save run `src/template_save.py`. The command used to skip the
  task-name check for library templates that the editor always made.
- `survey convert`: Studio's options and service run in the CLI; same flags, same defaults.

- Library choice, merge order and copying used templates into the project: one function for both
  (`src/survey_template_sources.py`).
- Dry-run: both leave the used templates in the project and write no data.
- Language maps: the converter picks the language for both; the CLI no longer compiles templates itself.
- Validation never rewrites `participants.tsv`.
