# Examples

Use this section when you want to learn PRISM Studio by doing rather than by
reading reference pages first.

The repository already contains reusable sample assets, and this page tells you
which example path to choose.

## Choose your example path

| If you want to... | Start here | Time |
|---|---|---|
| Get one quick success | [QUICK_START.md](QUICK_START.md) | 10 to 15 minutes |
| Learn the full beginner workflow | [WORKSHOP.md](WORKSHOP.md) | About 90 minutes |
| Reuse import templates only | `docs/examples/` sample files | A few minutes |
| Teach PRISM in a class or onboarding session | `examples/workshop/` handouts and exercises | 90 to 120 minutes |

## Recommended end-to-end example

The main recommended example path is the wellbeing workshop.

It takes a user through:

- project setup
- source-data conversion
- metadata completion and validation
- recipe-based scoring
- optional participant mapping and template work

Primary materials:

- RTD guide: [WORKSHOP.md](WORKSHOP.md)
- repository folder: `examples/workshop/`
- long-form handout: `examples/workshop/WORKSHOP_HANDOUT_WELLBEING.md`

## What is included in the repository

### Workshop package

The workshop folder contains:

- exercise folders for the core path
- optional extension exercises
- a full written handout
- a PDF version for teaching or offline use

### Import templates

The docs examples folder includes sample import files such as:

- `docs/examples/survey_import_template.xlsx`
- `docs/examples/biometrics_import_template.xlsx`

These are useful when you want a format reference without running the full
workshop.

## Recommended learning order

If you are new to the project, use this sequence:

1. [QUICK_START.md](QUICK_START.md)
2. [WORKSHOP.md](WORKSHOP.md)
3. [PROJECTS.md](studio/projects.md)
4. [SURVEY_IMPORT.md](studio/converter_survey.md)
5. [VALIDATOR.md](studio/validator.md)

That gives you one short success path first, then one fuller end-to-end example,
then the deeper workflow pages.

## Example outcomes you can expect

By the end of the main workshop flow, you should be able to:

- create a clean PRISM project
- import a sample survey dataset
- inspect and fix validation findings
- run a simple scoring recipe
- understand where project metadata, source data, and derivatives belong

## For instructors and maintainers

The workshop materials are also the best base for future documentation examples,
because they are concrete, repository-local, and easy to verify against current
behavior.

## Related pages

- [WORKSHOP.md](WORKSHOP.md)
- [QUICK_START.md](QUICK_START.md)
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)
