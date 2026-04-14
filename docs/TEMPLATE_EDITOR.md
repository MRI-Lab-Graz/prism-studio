# Template Editor

Use the Template Editor when you need to create, complete, or correct survey and biometrics templates.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## Where to find it

Open:

- PRISM Studio
- Tools
- Template Editor

## What the Template Editor does

The editor helps you work with PRISM JSON templates without editing raw JSON by hand.

Typical tasks are:

- load a project template
- load a global reference template
- create a new template
- import a template structure into the editor
- validate the current editor state
- save the result to the project library

## Project templates and global templates

The editor shows two different template sources:

- project templates
- global templates

Use project templates when you want to save changes.

Use global templates as read-only reference material. They help you start from an approved structure, but the normal save target is still your project library.

## Where Save goes

Save writes into the current project library.

For survey templates, that means:

- `code/library/survey/`

For biometrics templates, that means:

- `code/library/biometrics/`

This is important. The Template Editor does not use the official library as your normal save location.

## Recommended beginner workflow

1. Load your project first.
2. Open Template Editor.
3. Choose the correct modality.
4. Load a project template or a global reference template.
5. Make only the changes you need.
6. Run Validate.
7. Save to Project.

## When you usually need the editor

Most users use the editor in two situations:

- after survey import, when a copied project template still needs administration details
- when building a new project-local template for a custom instrument

## What to check in a survey template

The most useful beginner checks are:

- `Study` information is present
- `TaskName` is correct for the project copy
- `Technical` information matches how the survey was actually collected
- item descriptions and response options look correct

Do not try to fill every optional field in the first pass.

## Variant and version support

Some survey templates contain more than one version.

When that happens, the editor shows the version or variant controls for that template. Use them only if your instrument really has multiple forms.

If you are unsure, keep the simple single-version path.

## Import into the editor

The editor can also import structure into the current editing session.

For beginners, the important point is simple: import is a way to bring a structure into the editor for review, validation, and project-local save.

## Download and print options

The editor can also export the current template for download.

Depending on the workflow, this may include:

- JSON download
- questionnaire export as `.docx`

These exports are useful for checking or sharing the template state.

## Delete

Delete is for project-local templates.

Use it carefully. It is meant for removing templates from your project library, not from the official global library.

## Common beginner mistakes

- editing the wrong modality
- forgetting to validate before saving
- assuming a global template was edited directly
- forgetting to fill project-specific administration details after import
- making too many changes at once and losing track of what changed

## Related pages

- Template structure reference: [TEMPLATES.md](TEMPLATES.md)
- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- Projects: [PROJECTS.md](PROJECTS.md)
- Recipe-based scoring: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- Analysis and export outputs: [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)