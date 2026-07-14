# Workshop

Learn PRISM Studio through one concrete end-to-end example with repository-local
materials — the best path when you want more than Quick Start but don't want to jump
straight into reference pages. Takes you from a small source spreadsheet to a
validated and scored project: project setup, source-data conversion, validation and
metadata repair, and recipe-based scoring, with optional extensions for participant
mapping and template creation.

| Exercise | Topic | Time | Outcome |
|---|---|---|---|
| 0 | Project setup | 15 min | A clean project structure |
| 1 | Data conversion | 30 min | Survey data imported from Excel |
| 2 | Metadata and validation | 25 min | Validation findings understood and reduced |
| 3 | Recipes and scoring | 20 min | A simple score and export-ready result |
| Optional 4 | Templates | 20 min | Reusable survey metadata |
| Optional 5 | Participant mapping | 30–45 min | Standardized participant metadata |

Total: ~90 minutes for the core path, ~2 hours with extensions.

## Getting started

Materials live under `examples/workshop/` (`exercise_0_project_setup/` through
`exercise_5_participant_mapping/`, plus `WORKSHOP_HANDOUT_WELLBEING.md`/`.pdf` and
`WORKSHOP_README.md` as the best starting documents). Before you start: make sure
PRISM Studio launches (`source .venv/bin/activate && python prism-studio.py`), open
the workshop materials, and decide whether you want the core path only or the
extensions too.

## Core path

**Exercise 0 — Project setup**: create a clean project (e.g. `wellbeing_study`). Pay
attention to the project root structure and the separation of source data, validated
data, code, and derivatives.

**Exercise 1 — Data conversion**: convert
`examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx` into survey data
inside the project. Confirm the participant ID column and selected item columns,
preview before saving. Expect survey files written into subject-level folders.

**Exercise 2 — Metadata and validation**: see what the validator catches and how
richer metadata improves the dataset. Expect early findings like missing/incomplete
survey metadata, item descriptions, or response labels — use the provided template
material to complete metadata, then re-validate until major issues clear.

**Exercise 3 — Recipes and scoring**: compute one simple wellbeing score, e.g.:

```json
{
  "RecipeName": "Workshop Dummy Wellbeing",
  "Scoring": {
    "wellbeing_total": {
      "operation": "sum",
      "items": ["WB01", "WB02", "WB03", "WB04", "WB05"]
    }
  }
}
```

Expect one derived score and a clearer connection between imported raw responses
and downstream analysis outputs.

## Optional extensions

**Templates** — practice making the data self-documenting: item wording, translated
text, response options/labels, saving templates into the project library.

**Participant mapping** — standardize incoming demographic encodings: coded values
(`1/2/4`) to readable labels, text-based numeric values to canonical numeric form.

## Wrap-up

By the end of the core path you should have a project that loads cleanly, survey
files imported from the example spreadsheet, at least one validation-cleanup
iteration completed, and a simple scoring workflow demonstrated.

**For instructors**: this workshop works well for onboarding because it tells one
full story instead of isolated feature demos. Suggested pattern: show the raw
spreadsheet first → create the project live → import before discussing every schema
detail → use validation as the teaching moment for metadata quality → finish with
scoring or export as the payoff.

## What's next

- [Quick Start](QUICK_START.md)
- [Projects](studio/projects.md) · [Survey Import](studio/converter_survey.md) ·
  [Validator](studio/validator.md)
- [Recipes](RECIPES.md)
