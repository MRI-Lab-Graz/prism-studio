# Recipe Builder

Use the Recipe Builder when you want to turn raw questionnaire items into named
scores or other derived outputs.

This tool defines the scoring logic. It does not itself guarantee that the final
score files already exist.

## Where to find it

Open:

- PRISM Studio
- Prepare Data
- Recipe Builder

## What the Recipe Builder does

The Recipe Builder helps you:

- create total scores
- create subscales
- define reverse-coded items
- save reusable scoring definitions into the project

## Where recipes are saved

Project-local survey recipes are saved in:

- `code/recipes/survey/`

That file is the scoring definition. The scored outputs appear later when the
recipe is actually run.

## Recommended first recipe workflow

1. Load the correct project.
2. Open **Recipe Builder**.
3. Select the survey template that matches the imported data.
4. Review the available items.
5. Mark reversed items if the instrument requires them.
6. Add one score only.
7. Validate and save the recipe.
8. Run the scoring workflow and inspect the outputs.

One working total score is more useful than a large unfinished recipe with many
uncertain decisions.

## Choose the correct template first

The builder starts from the survey template context.

That means the recipe only makes sense if:

- the survey import matched the correct instrument
- the template reflects the correct questionnaire version
- the item names align with the imported data

If any of those are unclear, solve that first in Template Editor or survey import
before building scoring logic.

## Reverse coding

Some instruments need reversed items. The Recipe Builder usually exposes that as
an inversion step.

Do this before building the final score structure when the questionnaire requires
it. A wrong inversion decision can produce technically valid but scientifically
wrong scores.

## Add scales

Most first recipes should start with one scale.

Examples:

- one total score
- one stress score
- one depression score

Only add subscales or multiple score groups after the first single-score recipe
works correctly.

## Example: first wellbeing recipe

If the imported survey contains items `WB01` to `WB05`, a first beginner recipe
can be a single total score over those items.

Conceptual structure:

```json
{
	"RecipeVersion": "1.0",
	"Kind": "survey",
	"Survey": {
		"TaskName": "wellbeing"
	},
	"Scores": [
		{
			"Name": "wellbeing_total",
			"Method": "sum",
			"Items": ["WB01", "WB02", "WB03", "WB04", "WB05"]
		}
	]
}
```

This is a good first test because it is easy to explain and easy to verify.

## Variations and alternate scoring paths

Some recipes support named variations or multiple scoring versions.

Use that only when the instrument genuinely has more than one accepted scoring
path. If not, stay on the simplest path first.

## Validation before trust

Recipe validation checks whether the structure is internally coherent. It does
not replace the scientific judgment that the right items and scoring rules were
selected.

Good practice:

1. validate the recipe structure
2. save the recipe
3. run the scoring workflow
4. inspect the output columns and spot-check the values

## Saved recipe vs scored output

Keep this distinction clear:

- saved recipe: definition in `code/recipes/survey/`
- scored output: generated files in `derivatives/survey/`

Saving the recipe is not the same as generating the output.

## Common mistakes

- saving a recipe before verifying item selection
- confusing saved recipes with scored outputs
- mixing questionnaire versions in one recipe
- forgetting reverse coding where required
- trying to model too many scales before one simple score is proven

## Related pages

- [RECIPES.md](RECIPES.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)