# Template Editor

Use the Template Editor when you need to create, complete, or correct survey and
biometrics templates without editing raw JSON by hand.

This is the main tool for turning imported data into self-documenting project
metadata.

## Where to find it

Open:

- PRISM Studio
- Prepare Data
- Template Editor

## What the Template Editor does

The editor helps you:

- load project-local templates
- inspect official or global reference templates
- create a new template from a schema-aware structure
- validate the current template state
- save the result into the project library

## When you usually need it

Most users reach the Template Editor in one of two situations:

- after survey import, when a project-local template exists but still needs
	project-specific administration detail
- when building a new template for an instrument that is not yet fully defined
	for the project

## Project templates vs global templates

The editor exposes two important sources:

- **project templates**
- **global templates**

Use project templates when you intend to edit and save.

Use global templates as read-only starting points or reference material. Even if
you begin there, the normal save target is still your project library.

## Where Save writes

Save writes into the current project library, not the official library.

Typical save locations:

- survey templates: `code/library/survey/`
- biometrics templates: `code/library/biometrics/`

That distinction matters because the project-local copy is the version tied to
your actual dataset and workflow.

## Recommended workflow

1. Load the correct project.
2. Open **Template Editor**.
3. Choose the correct modality.
4. Load a project template or a global reference template.
5. Make only the needed changes.
6. Run **Validate**.
7. Save to the project.
8. Re-run dataset validation if the template affects imported data.

## What to check in a survey template

For a first pass, focus on the fields that usually matter most:

- `Study` information is present and coherent
- `TaskName` matches the project-level use of the instrument
- `Technical` information matches how the survey was actually collected
- item descriptions and response options are understandable

You do not need to complete every optional field on the first pass.

## Example: finishing a project-local survey template after import

Typical situation:

- survey data was imported successfully
- PRISM copied or created a project-local template
- validation still reports missing or incomplete survey metadata

Suggested path:

1. Open **Template Editor**.
2. Choose the survey modality.
3. Load the project template associated with the imported survey.
4. Confirm `TaskName`, language, and administration details.
5. Review item descriptions and response options.
6. Run **Validate**.
7. Save to project.
8. Re-run the main dataset validation.

Expected result:

- a more complete project-local template
- fewer template-related validation findings

## Variants and versions

Some survey templates have more than one version or variant.

Use the variant controls only when the instrument truly has multiple forms. If
you are unsure, keep the simpler single-version path until the instrument choice
is confirmed.

## Import into the editor

Import brings a structure into the editor for review, validation, and
project-local save. Treat it as an editing entry point, not as proof that the
template is already publication-ready.

## Download and export options

Depending on the workflow, the editor may let you export the current template as:

- JSON
- questionnaire-related document output such as `.docx`

These are useful for review and sharing, but the authoritative project state is
still the saved project-local template.

## Delete behavior

Delete applies to project-local templates.

Use it carefully. It is not intended as a way to modify the official global
library.

## Common mistakes

- editing the wrong modality
- assuming a global template was edited directly
- forgetting to validate before saving
- forgetting the project-specific `Technical` details after import
- making too many changes at once and losing track of what solved the issue

## Related pages

- [TEMPLATES.md](TEMPLATES.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [VALIDATOR.md](VALIDATOR.md)
- [RECIPE_BUILDER.md](RECIPE_BUILDER.md)