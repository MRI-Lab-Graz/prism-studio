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
- Studio-only backend calls the baseline lists (about 150): defacing export (`src.mri_json_scrubber`), the recipe builder's
  template analysis (`src.recipe_builder`), Neurobagel schema generation (`src.participant_columns`), physio renaming
  helpers (`src.physio_renamer`) and more. Each needs a look: does a CLI command run the same code?
- `app/src/web/validation.py` - Studio's validation has its own subprocess fallback path next to the core validator.

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
