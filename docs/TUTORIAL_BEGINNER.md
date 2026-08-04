# Getting Started — Your First PRISM Project

A self-paced, start-from-zero walkthrough for someone who has never opened
PRISM Studio before. Five chapters take you from an empty folder to a
validated, scored project, using one running example throughout so you never
have to switch mental models mid-tutorial.

This sits alongside two other on-ramps rather than replacing them: [Quick
Start](QUICK_START.md) is faster and assumes you'll fill in gaps yourself;
[Workshop](WORKSHOP.md) is the same core journey packaged for a live,
instructor-led session. Use this one if you want the most explanation and
plan to work through it alone.

**Time:** ~85 minutes for all five chapters. **Outcome:** one project
(`wellbeing_study`) with sociodemographic data, imported survey responses, a
working scoring recipe, and a clean validation run.

| Chapter | Topic | Time | Outcome |
|---|---|---|---|
| [1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md) | Create a project | ~15 min | A correctly-structured PRISM project with complete required metadata |
| [2](TUTORIAL_BEGINNER_2_PARTICIPANTS.md) | Import sociodemographic data | ~15 min | `participants.tsv` / `participants.json` |
| [3](TUTORIAL_BEGINNER_3_SURVEY_IMPORT.md) | Import a survey via Excel | ~25 min | Survey response files in subject folders |
| [4](TUTORIAL_BEGINNER_4_RECIPE.md) | Prepare a recipe | ~15 min | A saved, working scoring recipe and its output |
| [5](TUTORIAL_BEGINNER_5_VALIDATOR.md) | Use the validator | ~15 min | Validation findings understood and resolved |

## Prerequisites

- PRISM Studio installed and launchable — see [Installation](INSTALLATION.md)
  if you haven't done this yet.
- No prior PRISM knowledge assumed. No prior BIDS knowledge assumed either;
  the chapters explain BIDS-specific terms (`sub-`, sessions, sidecars) as
  they come up.

## One running example, start to finish

Every chapter uses the same fictional dataset, already included in the
repository under `examples/workshop/` — you don't need to create or download
anything extra:

- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx` — one
  spreadsheet with both demographic columns (age, sex, education,
  handedness) and five wellbeing-survey items (`WB01`-`WB05`) for the same
  fake participants. Chapter 2 uses the demographic columns; chapter 3 uses
  the survey items.
- `examples/workshop/exercise_4_templates/survey-wellbeing.json` — a
  ready-made survey template for the instrument used in chapter 3.
- `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json` — a
  working scoring recipe used as the worked example in chapter 4.

These are the same materials used by [Workshop](WORKSHOP.md) — if you've
already done that workshop, the data will look familiar, but this tutorial
explains each step in far more detail and at your own pace.

## What's next

Once you've completed all five chapters, an **Intermediate** tutorial
covering DataLad version control and bulk file/folder manipulation is
planned as the next step in this series — check back here once it's
published. In the meantime:

- [Studio Guide](studio/index.md) — full reference for every screen
- [CLI Reference](CLI_REFERENCE.md) — the same workflows from the terminal
- [Workshop](WORKSHOP.md) — the same journey as a guided group exercise
