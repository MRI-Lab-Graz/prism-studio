# Analysis Output

Use this page when you want to understand what PRISM produces after conversion, scoring, or export.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## The main idea

PRISM does not put every result into one folder.

Different outputs have different purposes:

- `code/` stores project-local templates, recipes, and scripts
- `derivatives/` stores processed outputs
- export workflows create separate shareable outputs

This is useful because it keeps raw or source material separate from processed results.

## The outputs most users will see

The most common outputs are:

- scored survey outputs in `derivatives/`
- methods boilerplate text
- shareable project exports
- ANC export folders
- openMINDS metadata export files

## 1. Scored survey outputs

When you run survey recipes, PRISM writes the results into `derivatives/survey/`.

Depending on the workflow, you may see:

- recipe-specific output folders
- a flat `survey_scores.tsv` output
- a derivative `dataset_description.json`

Think of this as processed analysis-ready data, not raw data.

## 2. Methods boilerplate

PRISM can also generate methods boilerplate from your project and recipe information.

This is useful for reports, theses, and early manuscript drafts.

Treat it as a starting text. You still need to review and polish it.

## 3. Shareable ZIP export

The Projects page includes a general export workflow for sharing a project.

This export can include:

- root project files
- subject folders
- `derivatives/`
- `code/`
- optionally `analysis/`

This is the easiest way to package a project for teaching, exchange, or archiving.

## 4. Anonymized export

If you need a shareable version without direct participant identifiers, use the anonymization options in the Projects export area.

Current options include:

- randomize participant IDs
- mask question text in JSON sidecars

This is especially useful before sharing work outside the study team.

Always review the export before distributing it.

## 5. ANC export

PRISM can create a dedicated ANC export folder.

This export is meant for Austrian NeuroCloud submission workflows. It creates a separate output folder ending in `_anc_export`.

Typical generated files include:

- `README.md`
- `CITATION.cff`
- `.bids-validator-config.json`

Use the separate ANC guide when you need submission details.

## 6. openMINDS export

The Projects page also includes an openMINDS metadata export.

This creates metadata output for openMINDS-oriented workflows. It is separate from the main PRISM dataset and separate from ANC export.

If you do not need openMINDS, you can ignore this section at the start.

## Which output should I use?

Use this rule of thumb:

- use `derivatives/` for processed results you still want inside the project
- use share/export tools when you want to hand results to other people or systems
- use ANC export only for ANC submission preparation
- use openMINDS export only when your workflow needs that metadata format

## Beginner workflow

For most users, this is enough:

1. import data
2. validate the dataset
3. run scoring if needed
4. check the output in `derivatives/`
5. export a shareable package only when the project is ready

## Common beginner mistakes

- looking in `analysis/` for every result
- editing derivative files by hand before validating the project
- sharing a project export without checking anonymization settings
- confusing saved recipes in `code/recipes/` with scored results in `derivatives/`

## Related pages

- Projects: [PROJECTS.md](PROJECTS.md)
- Recipe-based scoring: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- ANC export: [ANC_EXPORT.md](ANC_EXPORT.md)
- Template editing: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)