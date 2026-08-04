# Beginner Tutorial 4 — Prepare a Recipe

Chapter 4 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
This is about turning the five imported `WB01`-`WB05` responses into one
summary score per participant. Recipe Builder only creates and saves the
scoring definition; actually running it against your data happens on a
separate page, covered in step 5 below.

**Time:** ~15 minutes. **Outcome:** a saved scoring recipe for the
`wellbeing` survey, and a computed total score for every participant.

## 1. Open Recipe Builder

![PRISM Studio Recipe Builder screen](_static/screenshots/prism-studio-recipe-builder.png)

## 2. Pick modality and template

Set **Modality** to `survey`, then pick **Template**: `wellbeing` — the one
you saved into the project in [Chapter 3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md).

## 3. Skip reverse coding

The **Inversion** panel lets you reverse-code items against their scale
range. None of `WB01`-`WB05` need this — the WHO-5-style scale used here
already runs in the same direction for every item (higher = better
wellbeing) — so leave this panel empty.

## 4. Build the score

- In the **Item Pool**, select all five items: `WB01`-`WB05`.
- In the **Scale Canvas**, click **Add Scale** to create a new `Scores[]`
  entry:
  - **Name**: `Total`
  - **Method**: `sum`
  - **Items**: `WB01`, `WB02`, `WB03`, `WB04`, `WB05`
  - **Range**: each item runs 0-5 (six response levels), so five summed
    items give a range of **min 0, max 25** — fill in the range as
    item-scale × item-count, not by guessing.

You don't need `Transforms.Derived` here — a single summed total doesn't
need an intermediate helper computation.

## 5. Skip variations

**Variations** is for instruments with named scoring variants (e.g. a short
vs. long form). This tutorial's instrument has only one form, so leave this
step empty.

## 6. Fill in metadata and save

Under Recipe Metadata, give it a **Name** (e.g. "Wellbeing Total") and a
short **Description**. Click **Save**. This writes:

```text
code/recipes/survey/recipe-wellbeing.json
```

For comparison, a working version of this exact recipe already ships in the
repo at `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json` —
worth a look if your saved file's `Scores` block doesn't match what you
expected.

## 7. Run the recipe

Recipe Builder doesn't run recipes itself. Go to **Export / Analysis
Output**, pick modality `survey`, the session(s) to include (`baseline`),
and filter to your new recipe if more than one exists. Choose an output
format (`sav`/`csv`/`xlsx`) and click **Create Output**. Results land at:

```text
derivatives/survey/<recipe_id>/sub-*/ses-*/survey/*_desc-scores_beh.tsv   (per-subject)
derivatives/survey/survey_scores.tsv                                     (flat/wide, if chosen)
```

Equivalent from the terminal:

```bash
python prism_tools.py recipes surveys --prism /path/to/wellbeing_study --format prism
```

## Common mistakes

- **Item name mismatches** — the item names in the recipe must exactly match
  the template's `ItemID`s (`WB01`-`WB05`); a typo produces a save-time
  item-reference error, not a silent skip.
- **Forgetting Range** — the schema requires a `Range` on every `Scores`
  entry; derive it from the item scale rather than leaving it blank or
  copying an unrelated instrument's numbers.
- **Running the recipe before survey data exists** — Analysis Output has
  nothing to compute against if you skipped Chapter 3; import the survey
  data first.
- **Expecting Recipe Builder itself to produce output** — saving a recipe
  and running it are two different pages; Save only writes the definition.

## What's next

- [Chapter 5 — Use the validator](TUTORIAL_BEGINNER_5_VALIDATOR.md)
- [Recipe Builder](studio/recipe_builder.md) — full reference for this screen
- [Recipes](RECIPES.md) — the full `Transforms`/`Scores` specification
