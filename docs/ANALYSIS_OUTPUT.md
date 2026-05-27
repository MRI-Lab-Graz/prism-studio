# Analysis Output

Use this page to understand what PRISM produces after conversion, scoring, and
export workflows.

The main source of confusion here is usually not that outputs are missing. It is
that different outputs belong in different places for different reasons.

## The core principle

PRISM does not put every result into one folder because not every result serves
the same purpose.

Think in three buckets:

- `code/` for definitions and project-local assets
- `derivatives/` for processed outputs that still belong inside the project
- export outputs for packages intended to leave the project boundary

That separation helps keep source material, working definitions, and shareable
results distinct.

## The outputs most users will encounter

The most common outputs are:

- scored survey outputs in `derivatives/`
- methods boilerplate text
- shareable project exports
- anonymized exports
- ANC export folders
- openMINDS metadata export files

## 1. Scored survey outputs

When you run survey recipes, PRISM writes processed survey results into
`derivatives/survey/`.

Depending on the workflow, you may see:

- recipe-specific output folders
- files such as `survey_scores.tsv`
- derivative metadata such as a derivative `dataset_description.json`

Treat these as processed analysis-ready outputs, not as raw inputs.

## 2. Methods boilerplate

PRISM can generate methods text from project and instrument metadata.

Use this as:

- manuscript draft support
- report boilerplate
- a metadata completeness checkpoint

Treat it as draft text that still needs human review.

## 3. Shareable project export

The Projects page can create a shareable project package.

This may include:

- root project files
- subject folders
- `derivatives/`
- `code/`
- other configured project content depending on the export choice

This is the general packaging path for exchange, teaching, or archiving.

## 4. Anonymized export

Use anonymized export when you need to share the project beyond the immediate
study context.

Current user-facing goals can include:

- participant ID remapping
- privacy-oriented handling of metadata or question text depending on export settings

Important mental model:

- the export is the shareable copy
- the source project should remain the authoritative working dataset

Always review an anonymized export before distributing it.

## 5. ANC export

PRISM can create a dedicated ANC export folder for Austrian NeuroCloud-oriented
submission workflows.

Typical result:

- a separate output folder ending in `_anc_export`

Typical files may include:

- `README.md`
- `CITATION.cff`
- `.bids-validator-config.json`

Use [ANC_EXPORT.md](ANC_EXPORT.md) when this is your target workflow.

## 6. openMINDS export

PRISM also supports openMINDS-oriented metadata export workflows.

This is separate from:

- the main PRISM dataset
- ANC export
- ordinary shareable ZIP export

If your workflow does not require openMINDS, you can ignore this at the start.

## Which output should I use?

Use this quick rule:

| Goal | Use |
|---|---|
| Keep processed results inside the project | `derivatives/` |
| Share the project with another person or team | export workflows |
| Prepare ANC submission | ANC export |
| Prepare openMINDS-oriented metadata | openMINDS export |

## Example output flow

Typical path after a survey project reaches a stable state:

1. import survey data
2. validate the dataset
3. complete template details
4. save a scoring recipe
5. run scoring
6. inspect `derivatives/survey/`
7. export a shareable package only when the project is ready

Expected distinction:

- recipe definitions stay in `code/recipes/`
- scored files appear in `derivatives/`
- shareable packages are created by export workflows

## Common mistakes

- looking in `analysis/` for every result regardless of workflow
- editing derivative files by hand before the project is validated
- sharing an export without checking anonymization settings
- confusing saved recipes in `code/recipes/` with scored outputs in `derivatives/`

## Related pages

- [PROJECTS.md](PROJECTS.md)
- [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- [RECIPES.md](RECIPES.md)
- [ANC_EXPORT.md](ANC_EXPORT.md)