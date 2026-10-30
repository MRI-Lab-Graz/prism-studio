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
