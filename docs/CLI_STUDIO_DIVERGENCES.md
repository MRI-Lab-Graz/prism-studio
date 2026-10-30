---
orphan: true
---

# Where Studio and the CLI still differ

**These are bugs.** The rule (root `CLAUDE.md`): the CLI executes, Studio only triggers. Each entry is to be removed by
making Studio call the same backend function as the command, with the same options and defaults. Found by reading the code
and comparing options; not exhaustive. Add what you find, delete what you fix, and prove each fix with a test in
`tests/test_cli_studio_parity.py`.

## `survey convert`

| What | CLI | Studio |
|---|---|---|
| `force` default | off | **on** (`SurveyWorkflowStageOptions.force`) |
| `authors` default | none | empty tuple |
| strict levels | no flag | option |
| near-item matching (`allow_near_item_match`, `near_match_tasks`) | no flag | options |
| ID map file | no flag on `convert` | option |
| CSV separator | no flag | option |
| `skip_participants` | fixed on | option |

## Logic that lives in Studio only (no command runs it)

- `app/src/web/blueprints/conversion_survey_official_template_helpers.py` - checking which official templates match an
  uploaded file (`infer_tasks_against_official_templates`) and resolving the official library on its own
  (`resolve_official_survey_dir`).
- `app/src/web/validation.py` - Studio's validation has its own subprocess fallback path next to the core validator.

## Two implementations of the same thing

- **Saving a template**: the route `api_template_editor_save` (`tools_template_editor_blueprint.py`) and the command
  `library template-save` (`cli/commands/library.py`) each validate and write on their own. One shared function should do it.
- **Picking one language out of a multilingual template**: `src/survey_localize.py` (the converters) and
  `library_i18n.compile_survey_template` (`library i18n build`) are separate implementations.
- **Choosing a template library**: `resolve_survey_library` (a single folder, for the editor and validation) and
  `template_tiers` (the per-template merge for conversions) state the project, personal, global order twice.

## Fixed (keep the tests green)

- Library choice, merge order and copying used templates into the project: one function for both
  (`src/survey_template_sources.py`).
- Dry-run: both leave the used templates in the project and write no data.
- Language maps: the converter picks the language for both; the CLI no longer compiles templates itself.
- Validation never rewrites `participants.tsv`.
