# Recipes Reference

This page explains what a recipe is and where PRISM stores recipe definitions and recipe outputs.

For the step-by-step Studio workflow, use the Recipe Builder guide instead.

## What a recipe is

A recipe is a JSON file that tells PRISM how to turn raw items into computed scores.

Recipes can define:

- reverse coding
- intermediate derived values
- final score columns

## Current project recipe location

For survey workflows, saved project-local recipes belong in:

- `code/recipes/survey/`

Older folders may still exist in legacy projects, but this is the current project location to document and use.

## Two main parts

The most important sections are:

- `Transforms`
- `Scores`

`Transforms` handles preparation steps such as inversion or intermediate calculations.

`Scores` defines the final output columns you want to analyze.

## Derived values and final scores

`Transforms.Derived` acts like a scratch area.

These values help build the final scores, but they are not the main public result.

`Scores` defines the output variables that should appear in the scored files.

## Common methods

Common score methods include:

- `sum`
- `mean`
- `formula`
- `map`

Common derived methods include:

- `sum`
- `mean`
- `min`
- `max`
- `formula`
- `map`

## Missing data handling

Recipes can define how missing values should be handled.

Common options include:

- `ignore`
- `require_all`

Use `ignore` when a score may still be meaningful with a small amount of missing data.

Use `require_all` when every item must be present.

## Output location

When scoring runs successfully, PRISM writes survey outputs into:

- `derivatives/survey/`

You may see:

- recipe-specific output folders
- `survey_scores.tsv`
- derivative metadata such as `dataset_description.json`
- methods boilerplate files when that option is used

## Minimal example

```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": {
    "TaskName": "pss"
  },
  "Scores": [
    {
      "Name": "pss_total",
      "Method": "sum",
      "Items": ["PSS01", "PSS02", "PSS03"]
    }
  ]
}
```

## Beginner advice

Start with one small, testable score.

Once that works, add subscales, inversion, or more advanced logic.

## Related pages

- Recipe Builder workflow: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- Analysis and export outputs: [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- Survey templates: [TEMPLATES.md](TEMPLATES.md)