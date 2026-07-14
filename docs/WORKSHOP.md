# Workshop

Learn PRISM Studio through one concrete end-to-end example with repository-local
materials.

The workshop is the best path when you want more than the quick start but do not
want to jump straight into reference pages.

## What the workshop teaches

The workshop takes you from a small source spreadsheet to a validated and scored
project.

Core skills covered:

- project setup
- source-data conversion
- validation and metadata repair
- recipe-based scoring

Optional extensions:

- participant mapping
- template creation

## Time and structure

| Exercise | Topic | Time | Outcome |
|---|---|---|---|
| 0 | Project setup | 15 min | A clean project structure |
| 1 | Data conversion | 30 min | Survey data imported from Excel |
| 2 | Metadata and validation | 25 min | Validation findings understood and reduced |
| 3 | Recipes and scoring | 20 min | A simple score and export-ready result |
| Optional 4 | Templates | 20 min | Reusable survey metadata |
| Optional 5 | Participant mapping | 30 to 45 min | Standardized participant metadata |

Total: about 90 minutes for the core path, or about 2 hours with extensions.

## Workshop materials

Repository folder:

```text
examples/workshop/
├── exercise_0_project_setup/
├── exercise_1_raw_data/
├── exercise_2_hunting_errors/
├── exercise_3_using_recipes/
├── exercise_4_templates/
├── exercise_5_participant_mapping/
├── WORKSHOP_HANDOUT_WELLBEING.md
└── WORKSHOP_HANDOUT_WELLBEING.pdf
```

Best starting documents:

- `examples/workshop/WORKSHOP_HANDOUT_WELLBEING.md`
- `examples/workshop/WORKSHOP_README.md`

## Before you start

1. Make sure PRISM Studio launches correctly.
2. Open the repository-local workshop materials.
3. Decide whether you want the core path only or the optional extensions too.

Launch Studio from repository root if needed:

```bash
source .venv/bin/activate
python prism-studio.py
```

## Core path

### Exercise 0: Project setup

Goal: create a clean project such as `wellbeing_study`.

What to pay attention to:

- project root structure
- separation of source data, validated data, code, and derivatives
- where study-level metadata lives

### Exercise 1: Data conversion

Goal: convert the example spreadsheet into survey data inside the project.

Main source file:

- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`

Key checks during the exercise:

- confirm the participant ID column
- confirm the selected item columns
- preview before saving

Expected output:

- survey files written into subject-level folders

### Exercise 2: Metadata and validation

Goal: understand what the validator catches and how richer metadata improves the
dataset.

Expected early findings:

- missing or incomplete survey metadata
- missing item descriptions
- missing response labels

Typical next step:

- use the provided template material to complete the metadata
- run validation again until the major issues are resolved

### Exercise 3: Recipes and scoring

Goal: compute one simple wellbeing score.

Conceptual recipe example:

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

Expected outcome:

- one derived score
- a clearer connection between imported raw responses and downstream analysis outputs

## Optional extension paths

### Templates

Use this when you want to practice making the data self-documenting.

Focus on:

- item wording
- translated text
- response options and labels
- saving templates into the project library

### Participant mapping

Use this when you want to standardize incoming demographic encodings.

Typical transformations:

- coded values such as `1/2/4` to readable labels
- text-based numeric values to canonical numeric form

## What success looks like

By the end of the core path you should have:

- a project that loads cleanly
- survey files imported from the example spreadsheet
- at least one validation-cleaner iteration completed
- a simple scoring workflow demonstrated

## Instructor notes

This workshop works well for onboarding because it gives participants one full
story instead of isolated feature demos.

Recommended teaching pattern:

1. show the raw spreadsheet first
2. create the project live
3. import before discussing every schema detail
4. use validation as the teaching moment for metadata quality
5. finish with scoring or export as the payoff step

## Related pages

- [QUICK_START.md](QUICK_START.md)
- [PROJECTS.md](studio/projects.md)
- [SURVEY_IMPORT.md](studio/converter_survey.md)
- [VALIDATOR.md](studio/validator.md)
- [RECIPES.md](RECIPES.md)
