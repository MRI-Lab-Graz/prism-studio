# Recipes Reference

The reference model for PRISM scoring recipes, rather than the step-by-step UI
workflow — for the guided editor, use [Recipe Builder](studio/recipe_builder.md).

## Concepts

A recipe is a JSON definition telling PRISM how to turn raw survey items into
derived values and final scores: reverse coding, intermediate derived values, final
score columns, missing-data behavior.

Keep the **recipe definition** (saved in the project, `code/recipes/survey/`)
distinct from the **computed result** (written when the recipe is executed,
`derivatives/survey/`).

## Structure: Transforms and Scores

Two main areas:

- **`Transforms`** — preparation logic: inversion, intermediate calculations, helper
  variables supporting the final scores. Common methods: `sum`, `mean`, `min`,
  `max`, `formula`, `map`.
- **`Scores`** — the final, analysis-facing output columns you want to keep and
  interpret; this is usually what becomes the main analysis output. Common methods:
  `sum`, `mean`, `formula`, `map`.

Derived values are useful for intermediate logic but aren't automatically the main
result you report — that's what `Scores` is for.

## Missing-data handling

Common choices: `ignore` (a score can still be meaningful with limited missing data)
or `require_all` (every item must be present).

## Example and design process

```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": { "TaskName": "pss" },
  "Scores": [
    { "Name": "pss_total", "Method": "sum", "Items": ["PSS01", "PSS02", "PSS03"] }
  ]
}
```

This is the right scale for a first example — easy to test and spot-check against
raw item values. Good progression: start with one simple score → confirm the item
list is correct → confirm reverse coding if required → add derived values/subscales
only after the simple case works.

When scoring runs successfully, outputs may include recipe-specific output folders,
`survey_scores.tsv`, derivative metadata (`dataset_description.json`), and
methods-related outputs when enabled.

## Common mistakes

Treating a saved recipe as if it already generated outputs; building many scales
before one simple score is verified; mixing questionnaire versions in one recipe;
forgetting that missing-data policy changes the meaning of the score.

## What's next

- [Recipe Builder](studio/recipe_builder.md)
- [Export](studio/export.md)
- [Survey Import](studio/converter_survey.md)
