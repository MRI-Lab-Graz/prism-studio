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

A score may also carry two optional plain-text notes about its direction:

- **`HigherMeans`** - what a higher score means, for example `more fatigue`.
- **`LowerMeans`** - what a lower score means, for example `less fatigue`.

Derived values are useful for intermediate logic but aren't automatically the main
result you report — that's what `Scores` is for.

## Missing-data handling

An answer is missing when the cell is empty, `n/a` or not a number.

- A **`sum`** is left empty (`n/a`) when *any* item is missing - a total over only some of the items is
  not comparable with a complete one. This is the default (`Missing: "require_all"`, aliases `all`, `strict`).
- A **`mean`** uses the answered items by default (`Missing: "ignore"`).
- `Missing: "ignore"` on a `sum` opts back in to summing only the answered items (the sum of 3 of 5 items is
  lower than a complete response).
- `MinValid: N` - the score is left empty (`n/a`) if fewer than N items are answered. For a `sum`
  combine it with `Missing: "ignore"`, otherwise every item is still required.

`formula` scores are left empty whenever any item they use is missing (earlier versions
treated a missing item as 0, so an unanswered questionnaire scored 0). Recipe Builder
offers these as one choice per scale, "If answers are missing".

## Formulas (`Method: "formula"`)

When a score is more than a sum or mean, write it as a formula.

**In the Recipe Builder:** set a score's Method to `formula`, pick items from the pull-down (they move into
chips and insert `{ITEM}` in the formula box), and type the formula. Under the box you see the rendered
formula and a check line: enter example values and it shows the result, or why the score would be empty
(unknown item, missing value, division by zero). The "Best of N" section writes `Transforms.Derived`
entries (`max`/`min`), whose names can then be used as items in a formula. The same check and rendering run
from the command line: `prism_tools recipes formula-check` and `recipes formula-latex`.
Rendering is display only; the recipe always stores the plain `Formula` string.
The example-value boxes under the formula (one labelled box per item) feed the check; for a Best of N
entry type its best value. Entries appear in the same "Add an item..." pull-down as ordinary items. The
builder's help block "How formulas and best-of work" shows these examples.

```json
{ "Name": "bmi", "Method": "formula", "Items": ["weight_kg", "height_m"],
  "Formula": "{weight_kg} / {height_m} ** 2" }
```

- **Examples:** BMI `{weight_kg} / {height_m} ** 2`; mean of both sides
  `({ybt_comp_left} + {ybt_comp_right}) / 2`.
- **`Items`** lists every column the formula uses; **`{NAME}`** in `Formula` is replaced by that
  column's value. A name used in `Formula` but missing from `Items` is not replaced and the score
  is left empty.
- **Operators:** `+ - * / ** %`, brackets, comparisons (`< <= > >= == !=`), `and`, `or`.
- **Functions:** `min`, `max`, `sum`, `abs`, `round`, `sqrt`, `exp`, `log`, and
  `ifelse(condition, value_if_true, value_if_false)`.
- **Missing data:** the score is left empty if any column in `Items` is missing (see above).
- **Chaining:** an item may be a `Transforms.Derived` entry or an earlier `Scores` entry. Derived
  values are calculated first, scores in the order written.
- **Participant variables:** every column of the project's `participants.tsv` (except
  `participant_id`) can be used like an item, for example `{age}` or
  `ifelse({sex} == "F", {total} - 2, {total})`; the formula pull-down marks them "(participant)".
  A questionnaire item of the same name wins. They cannot be reverse-scored. A recipe that names a
  column the project does not have is an error.
- Formulas are evaluated by a restricted calculator, never as code; anything else in a formula
  leaves the score empty.

### Worked example: Y Balance Test

Each direction is tried three times per leg; the best trial counts, and the composite is the mean
of the three best values, optionally relative to leg length (`leg_length_right`, one column per
participant and session).

```json
"Transforms": { "Derived": [
  { "Name": "ybt_ant_right", "Method": "max", "Items": ["ant_r_1", "ant_r_2", "ant_r_3"] },
  { "Name": "ybt_pm_right",  "Method": "max", "Items": ["pm_r_1",  "pm_r_2",  "pm_r_3"] },
  { "Name": "ybt_pl_right",  "Method": "max", "Items": ["pl_r_1",  "pl_r_2",  "pl_r_3"] }
] },
"Scores": [
  { "Name": "ybt_composite_right", "Method": "formula",
    "Items": ["ybt_ant_right", "ybt_pm_right", "ybt_pl_right"],
    "Formula": "({ybt_ant_right} + {ybt_pm_right} + {ybt_pl_right}) / 3" },
  { "Name": "ybt_composite_right_rel", "Method": "formula",
    "Items": ["ybt_ant_right", "ybt_pm_right", "ybt_pl_right", "leg_length_right"],
    "Formula": "({ybt_ant_right} + {ybt_pm_right} + {ybt_pl_right}) / (3 * {leg_length_right}) * 100" }
]
```

Use a **`Transforms.Derived`** entry with `Method: "max"` (or `"min"`) for "best of N trials": it skips a missing
trial. `max` as a *score* method is not supported (the score stays empty), and `max(...)` inside a
formula is empty when any trial is missing. Use `Transforms.Derived` for best-of-N.

### Choosing a condition: `ifelse`

```json
{ "Name": "high_fatigue", "Method": "formula", "Items": ["fatigue_total"],
  "Formula": "ifelse({fatigue_total} >= 30, 1, 0)" }
```

## Example and design process

```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": { "TaskName": "demo" },
  "Scores": [
    { "Name": "demo_total", "Method": "sum", "Items": ["DEMO01", "DEMO02", "DEMO03"] }
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

## Response variability (IRV)

Tick **Add response variability (IRV) per subject** in the Recipe Builder (or add
`{ "Name": "IRV", "Method": "irv", "Items": [...] }` to `Scores` by hand). It adds one
column: the standard deviation of that person's *raw* answers across the items
(reverse-coding is ignored). `0` means the same answer to every question, which can
indicate straight-lining but is a flag to review, not proof. It is empty with fewer than
two answered items; `MinValid` works as for other scores.

## Common mistakes

Treating a saved recipe as if it already generated outputs; building many scales
before one simple score is verified; mixing questionnaire versions in one recipe;
forgetting that missing-data policy changes the meaning of the score.

## What's next

- [Recipe Builder](studio/recipe_builder.md)
- [Export](studio/export.md)
- [Survey Import](studio/converter_survey.md)
