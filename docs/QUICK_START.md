# Quick Start

This guide is the shortest path from install to a first successful PRISM Studio
workflow.

Goal for this page:

1. launch Studio
2. create a project
3. import one small dataset
4. validate it
5. inspect the result and know what to do next

If you want a longer exercise with prepared sample material, continue with
[WORKSHOP.md](WORKSHOP.md) after this page.

## Step 1: Launch PRISM Studio

### Option A: use the pre-built release

1. Open the releases page: https://github.com/MRI-Lab-Graz/prism-studio/releases
2. Download the package for your operating system.
3. Extract the archive.
4. Launch PRISM Studio from the extracted folder.

This is the recommended path for most users.

### Option B: run from the source repository

From the repository root:

```bash
source .venv/bin/activate
python prism-studio.py
```

or:

```bash
source .venv/bin/activate
rtk studio
```

Studio should open at `http://localhost:5001`.

## Step 2: Create your first project

1. Open **Projects**.
2. Select **Create New Project**.
3. Enter a project name such as `my_first_study`.
4. Choose a parent folder.
5. Confirm creation.

You now have a project that can hold metadata, source material, validated data,
recipes, and derivatives in one place.

Typical structure:

```text
my_first_study/
├── dataset_description.json
├── project.json
├── CITATION.cff
├── CHANGES
├── README.md
├── .bidsignore
├── .prismrc.json
├── sourcedata/
├── derivatives/
└── code/
```

`participants.tsv` is not created yet at this point — it is written once you run the
sociodemographics/participants import step.

If you plan to work with larger datasets or provenance tracking, read
[DATALAD.md](DATALAD.md) before reshaping the project manually.

## Step 3: Import a small example dataset

The simplest first success is to use the workshop sample material.

Recommended sample source:

- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`

### Survey example

1. Open **Converter**.
2. Choose the survey workflow.
3. Select `wellbeing.xlsx`.
4. Confirm the participant ID column.
5. Select the wellbeing item columns.
6. Preview the output.
7. Save the converted result into your project.

Expected outcome:

- survey files written into subject folders
- a project that now contains importable or validatable data

### Participants example

If you start with sociodemographics instead, pick the correct case first:

- **Case 1**: the imported file becomes the source of truth
- **Case 2**: you are editing an existing project file
- **Case 3**: you want a safe merge

Use [PARTICIPANTS_MAPPING.md](studio/converter_participants.md) if you are unsure which
case applies.

## Step 4: Run validation

1. Open **Validator**.
2. Select your project folder if it is not already active.
3. Enable BIDS validation too if you want the broader check.
4. Click **Validate**.

You will see findings grouped by severity.

| Level | Meaning | What to do |
|---|---|---|
| Error | Blocking problem | Fix it before treating the dataset as valid |
| Warning | Important issue | Fix soon, especially before sharing |
| Suggestion | Improvement | Use when polishing the dataset |

Common first findings:

| Example code | Meaning | Typical fix |
|---|---|---|
| `PRISM101` | Missing sidecar JSON | Add the matching `.json` sidecar |
| `PRISM201` | Invalid filename | Rename to the expected BIDS/PRISM pattern |
| `PRISM301` | Missing required metadata field | Complete the required JSON field |

Open the finding details before changing files blindly. The codes are much more
useful when you read them as workflow feedback instead of just error labels.

## Step 5: Check the result in the project

After a successful first pass, you should have:

- a project root with the usual study-level files
- at least one imported data slice
- a validation result you can inspect or re-run

If your validation still shows missing metadata, that is normal for a first run.
The next common step is to complete survey or biometrics templates and then run
validation again.

## Step 6: Optional first scoring pass

If your survey data is ready, continue with a simple recipe flow:

1. Open **Prepare Data**.
2. Open **Recipe Builder**.
3. Load or create a small scoring recipe.
4. Run it against your project.
5. Export the result as CSV or SPSS if needed.

See [RECIPE_BUILDER.md](studio/recipe_builder.md) and [RECIPES.md](RECIPES.md) for the
deeper workflow.

## Equivalent CLI checks

If you prefer to confirm the same project from the terminal:

```bash
prism-validator /path/to/project --bids
```

For broader command coverage, see [CLI_REFERENCE.md](CLI_REFERENCE.md).

## Common first-time issues

### No files found in the dataset

Check that your data ended up in the project dataset structure, not only in a
source-material folder.

### Missing `dataset_description.json`

Projects normally create this for you. If it is missing, your project creation
step likely did not complete correctly.

### Invalid filename pattern

The validator expects BIDS-style entities in filenames, for example:

```text
sub-001_task-wellbeing_survey.tsv
sub-001_ses-01_task-wellbeing_survey.tsv
```

### Studio starts but no page appears

Open `http://localhost:5001` manually and check the terminal output for launch
errors.

## What to do next

- [STUDIO_OVERVIEW.md](studio/index.md) for the full page map
- [PROJECTS.md](studio/projects.md) for project and metadata workflows
- [SURVEY_IMPORT.md](studio/converter_survey.md) for a deeper survey conversion guide
- [WORKSHOP.md](WORKSHOP.md) for a longer guided exercise
