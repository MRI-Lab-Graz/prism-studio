# Recipes Reference

Use this page when you need the reference model for PRISM scoring recipes rather
than the step-by-step UI workflow.

For the guided editor workflow, use [RECIPE_BUILDER.md](RECIPE_BUILDER.md).

## What a recipe is

A recipe is a JSON definition that tells PRISM how to turn raw survey items into
derived values and final scores.

Recipes can describe:

- reverse coding
- intermediate derived values
- final score columns
- missing-data behavior

## Saved recipe vs output data

Keep this distinction clear:

- the **recipe definition** is saved in the project
- the **computed result** is written later when the recipe is executed

Current survey recipe path:

- `code/recipes/survey/`

Current survey output path:

- `derivatives/survey/`

## Main structural ideas

The two most important recipe areas are:

- `Transforms`
- `Scores`

### `Transforms`

Use this area for preparation logic such as:

- inversion
- intermediate calculations
- helper variables that support the final scores

### `Scores`

Use this area for the final analysis-facing output columns you want to keep and
interpret.

## Derived values vs final scores

Derived values are useful when you need intermediate logic, but they are not
automatically the main result you report.

The `Scores` section is what usually becomes the main analysis output.

## Common methods

Common final-score methods include:

- `sum`
- `mean`
- `formula`
- `map`

Common transform or derived methods include:

- `sum`
- `mean`
- `min`
- `max`
- `formula`
- `map`

## Missing-data handling

Recipes can define how missing values should behave.

Common choices include:

- `ignore`
- `require_all`

Use `ignore` when a score can still be meaningful with limited missing data.
Use `require_all` when every item must be present.

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

This is the right scale of first example because it is easy to test and easy to
spot-check against the raw item values.

## How to reason about recipe design

Good progression:

1. start with one simple score
2. confirm the item list is correct
3. confirm reverse coding if required
4. add derived values or subscales only after the simple case works

## Typical outputs after execution

When scoring runs successfully, survey outputs may include:

- recipe-specific output folders
- `survey_scores.tsv`
- derivative metadata such as `dataset_description.json`
- methods-related outputs when enabled by the workflow

## Common mistakes

- treating a saved recipe as if it already generated outputs
- building many scales before one simple score is verified
- mixing questionnaire versions in one recipe
- forgetting that missing-data policy changes the meaning of the score

## Related pages

- [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)