# Examples

For learning PRISM Studio by doing rather than reading reference pages first. The
repository has reusable sample assets — this page tells you which path to choose.

## Choose your path

| If you want to... | Start here | Time |
|---|---|---|
| Get one quick success | [Quick Start](QUICK_START.md) | 10–15 min |
| Learn the full beginner workflow | [Workshop](WORKSHOP.md) | ~90 min |
| Reuse import templates only | `docs/examples/` sample files | A few minutes |
| Teach PRISM in a class or onboarding session | `examples/workshop/` handouts and exercises | 90–120 min |

## What's in the repository

The main recommended end-to-end example is the wellbeing workshop — project setup,
source-data conversion, metadata completion and validation, recipe-based scoring,
optional participant mapping and template work. Materials: the
[Workshop](WORKSHOP.md) guide, the `examples/workshop/` folder (exercise folders for
the core path plus optional extensions, a full written handout, and a PDF for
teaching/offline use), and the long-form
`examples/workshop/WORKSHOP_HANDOUT_WELLBEING.md`.

For a format reference without running the full workshop, `docs/examples/` has
sample import files: `survey_import_template.xlsx`, `biometrics_import_template.xlsx`.

These materials are also the best base for future documentation examples — concrete,
repository-local, and easy to verify against current behavior.

## Recommended order and outcomes

If you're new: [Quick Start](QUICK_START.md) → [Workshop](WORKSHOP.md) →
[Projects](studio/projects.md) → [Survey Import](studio/converter_survey.md) →
[Validator](studio/validator.md). That gives you one short success first, then one
fuller end-to-end example, then the deeper workflow pages.

By the end of the main workshop flow you should be able to: create a clean PRISM
project, import a sample survey dataset, inspect and fix validation findings, run a
simple scoring recipe, and understand where project metadata, source data, and
derivatives belong.
