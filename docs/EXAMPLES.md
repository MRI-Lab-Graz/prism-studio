# Examples

For learning PRISM Studio by doing rather than reading reference pages first. The
repository has reusable sample assets — this page tells you which path to choose.

## Choose your path

| If you want to... | Start here | Time |
|---|---|---|
| Get one quick success | [Quick Start](QUICK_START.md) | 10–15 min |
| Learn the full beginner workflow | [Getting Started](TUTORIAL_BEGINNER.md) | ~130 min |
| Build a survey template from an Excel codebook | [Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md), then [— Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md) | 15–35 min |
| Reuse import templates only | `docs/examples/` sample files | A few minutes |
| Teach PRISM in a class or onboarding session | [Workshop](WORKSHOP.md) | 2–3 h |

## What's in the repository

The main recommended end-to-end example is the wellbeing study — project setup,
source-data conversion, metadata completion and validation, recipe-based scoring,
participant mapping and template work. It is taught once, as
[Getting Started](TUTORIAL_BEGINNER.md); its data files live in
`examples/workshop/`, one folder per chapter that needs them, with a run sheet in
`examples/workshop/README.md`. To teach it live, see [Workshop](WORKSHOP.md).

For a format reference without running the full workshop, `docs/examples/` has
sample import files: `survey_import_template.xlsx`, `biometrics_import_template.xlsx`.

For turning a spreadsheet codebook into a reusable survey **template** (instrument
definition, not respondent data), see
[Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md) and
[— Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md), backed by worked examples under
`examples/excel_template/`.

These materials are also the best base for future documentation examples — concrete,
repository-local, and easy to verify against current behavior.

## Recommended order and outcomes

If you're new: [Getting Started](TUTORIAL_BEGINNER.md) → [Workshop](WORKSHOP.md) →
[Projects](studio/projects.md) → [Survey Import](studio/converter_survey.md) →
[Validator](studio/validator.md). That gives you one short success first, then one
fuller end-to-end example, then the deeper workflow pages.

By the end of the main workshop flow you should be able to: create a clean PRISM
project, import a sample survey dataset, inspect and fix validation findings, run a
simple scoring recipe, and understand where project metadata, source data, and
derivatives belong.
