# Survey Library

Use this page to understand what the survey library is for and how it relates to
project-local template work.

## What the survey library is

The survey library is the collection of questionnaire templates PRISM can use as
reference material.

It helps with:

- consistent questionnaire structure
- reusable metadata
- faster lookup of known instruments
- cleaner project-local template creation

## Official library vs project copy

The key distinction is simple:

- the **official library** is the reference source
- the **project copy** is the editable working version for your dataset

Official library location:

- `official/library/survey/`

Project-local working location:

- `code/library/survey/`

For most users, the official library is something you select from, not something
you edit directly.

## What the library is useful for in practice

Most users need the library for one of these tasks:

- finding an existing instrument template
- starting from a trusted structure instead of a blank file
- copying a template into a project workflow
- checking item wording, scale labels, or available languages

## Bilingual and multi-language templates

Many library templates support more than one language in the same JSON structure.

That allows one instrument definition to carry multiple language variants without
duplicating the whole file for each language.

## Recommended user workflow

For most projects, the easiest pattern is:

1. find the matching survey in the library
2. copy or load it into the project workflow
3. complete the project-specific details in the project copy
4. validate before continuing

## Multi-version surveys

Some instruments have multiple versions or forms.

PRISM can represent those inside one template structure, but that means you
should confirm the correct version during import and editing rather than assuming
the first matching name is enough.

## What this page is not

This page is not the editing guide.

Use these pages next when you are doing real work rather than orientation:

- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [TEMPLATES.md](TEMPLATES.md)

## Common mistakes

- editing the official library when a project-local copy should be used instead
- assuming a copied template is already fully project-ready
- forgetting to validate after changing project-local template details

## Related pages

- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [TEMPLATES.md](TEMPLATES.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [SURVEY_VERSION_PLAN.md](SURVEY_VERSION_PLAN.md)