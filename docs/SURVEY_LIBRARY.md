# Survey Library

Use this page to understand what the survey library is for.

This page is written for beginners. Use the written guide here for the full context. Use the companion videos for quick hands-on examples.

## What the survey library is

The survey library is the collection of survey templates that PRISM can use as reference material.

These templates help with:

- consistent questionnaire structure
- consistent metadata
- reuse across multiple projects
- easier template lookup inside PRISM Studio

## Where the official library lives

The official library is stored in:

- `official/library/survey/`

This is the reference collection that ships with the project.

## What users usually need to know

For normal project work, the most important idea is simple:

- the official library is the reference source
- your project uses project-local copies when you actually edit or complete templates

That means most users do not need to modify the official library directly.

## Global template vs project template

Use this rule:

- global or official template: reference
- project template: editable working copy for your own dataset

When PRISM copies a template into your project, you continue working with the project-local version.

## Bilingual templates

Many survey templates support more than one language in the same JSON structure.

This helps keep the instrument definition in one place instead of duplicating the whole file for each language.

For beginners, the important point is that the template may already contain both German and English text.

## What the library is good for in practice

Most users use the survey library for one of these reasons:

- find an existing questionnaire template
- start from a structured example
- copy a known template into a project
- check item wording or response options

## What this page is not

This page is not the step-by-step editing guide.

For actual editing work, use:

- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)

For import workflows, use:

- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)

## Beginner workflow

For most user projects, the easiest pattern is:

1. find the matching survey in the library
2. import or copy it into the project workflow
3. complete the project-specific template details
4. validate before continuing

## Multi-version surveys

Some questionnaires have more than one version.

PRISM can represent these versions inside one template. If your survey has multiple forms, check the version carefully during import or editing.

If your survey has only one form, you can ignore this part at the start.

## Maintenance scripts

There are also maintenance tools for updating library metadata at the repository level.

Most beginners do not need these scripts. They are more relevant for maintaining the shared library itself.

## Related pages

- Template editing workflow: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Template structure reference: [TEMPLATES.md](TEMPLATES.md)
- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- Survey versioning: [SURVEY_VERSION_PLAN.md](SURVEY_VERSION_PLAN.md)