# Recipe Builder

Use the Recipe Builder when you want to create or edit scoring rules for survey data.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## Where to find it

Open:

- PRISM Studio
- Tools
- Recipe Builder

## What the Recipe Builder does

The Recipe Builder helps you define how raw questionnaire items become scores.

Typical uses are:

- create a total score
- create subscales
- reverse-code selected items
- save the scoring recipe into the project

## Where recipes are saved

Project-local survey recipes are saved in:

- `code/recipes/survey/`

This is the current working location for saved recipes in a project.

## Recommended beginner workflow

1. Load your project first.
2. Open Recipe Builder.
3. Select the survey template.
4. Review the available items.
5. Mark inverted items if needed.
6. Add one score at a time.
7. Save the recipe.

Keep the first recipe small. One working total score is better than a large unfinished recipe.

## Choose the survey template

The builder starts from a survey template.

You can work from:

- project templates
- optionally the official library view

For actual project work, save the recipe into the project after you are done.

## Inversion

Some questionnaires need reverse-coded items.

The builder includes an inversion area where you can select the items that need to be flipped. Do this before building the score structure if your questionnaire requires it.

## Add scales

Most users start with a single scale.

Examples:

- one total score
- one depression score
- one stress score

Add a clear scale name and then attach the correct items.

## Variations

Some recipes support named variations.

Use this only when your questionnaire really has more than one scoring version. If you do not need it, stay with the default path.

## Validate before trusting the output

The save workflow validates the recipe structure.

If something is missing or malformed, fix it before moving on. This prevents broken recipes from silently staying in the project.

## After saving

Saving the recipe does not mean the score output already exists.

The saved recipe is the scoring definition. The actual score files appear later when you run the scoring workflow.

Those outputs are written into `derivatives/survey/`.

## Common beginner mistakes

- saving a recipe before checking item selection carefully
- confusing saved recipes with scored outputs
- mixing questionnaire versions in one recipe
- forgetting reverse coding where it is required
- building too many scales before testing one simple score first

## Related pages

- Recipe reference: [RECIPES.md](RECIPES.md)
- Analysis and export outputs: [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- Template editing: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- Projects: [PROJECTS.md](PROJECTS.md)