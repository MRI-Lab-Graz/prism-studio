# Converter

Use the Converter to turn source files into PRISM/BIDS-compatible project data.

This is where spreadsheets, exports, and other source tables stop being raw
inputs and become structured data inside the project.

## What the Converter is for

The Converter supports multiple import paths, including:

- sociodemographics and participants files
- survey data
- biometrics
- physiology
- environment-style tabular inputs

For most first-time users, the two most important tabs are:

- **Sociodemographics**
- **Survey**

## Recommended order

The safest beginner sequence is:

1. open the correct project first
2. import or review participants data
3. import survey data
4. run validation

That order reduces downstream confusion in scoring, metadata, and export steps.

## Before you save anything

Check these four things every time:

- the correct project is active
- the source file is the one you intended to use
- the participant ID column is correct
- the preview looks right before saving

Preview-first behavior is one of the main protections against importing the
wrong structure into the project.

## Which converter path should you use?

| If your source looks like... | Start here | Why |
|---|---|---|
| A demographics or participant spreadsheet | Sociodemographics | Creates or updates `participants.tsv` and `participants.json` |
| A questionnaire export or item table | Survey | Creates subject-level survey files and sidecars |
| Performance-testing tables | Biometrics | Routes structured biometrics data into PRISM-compatible outputs |
| Signal or recording tables | Physio | Handles physiology-oriented import paths |
| Environmental context tables | Environment | Creates structured context data from tabular sources |

## Sociodemographics: the three-case decision

The participants workflow is organized around three explicit cases.

| Case | Use it when... | Risk profile |
|---|---|---|
| Case 1: Import file as source of truth | You want the imported table to define or replace the project participant files | Straightforward, but replacing existing files is a strong action |
| Case 2: Modify existing project files | The project files already exist and should stay the source of truth | Lowest risk when you only want to refine metadata or annotations |
| Case 3: Safe merge from imported file | You want to add new rows or fill missing values from another table | Highest risk, so the preview and conflict review matter most |

If you are unsure, read [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md)
before writing files.

## Survey import: the usual next step

After participants data is in place, survey import is the next common workflow.

Typical survey input sources include:

- Excel
- CSV
- TSV
- SPSS exports
- LimeSurvey exports

The survey workflow normally asks you to confirm:

- the participant identifier column
- the survey items or relevant columns
- task or naming context
- the preview before save

Use [SURVEY_IMPORT.md](SURVEY_IMPORT.md) for the detailed survey guide.

## Example workflow: from workshop spreadsheet to validated project

Example source files:

- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`
- a demographics source table, if available for the project

Recommended sequence:

1. Open the target project in **Projects**.
2. In **Converter**, start with **Sociodemographics** if participant files do not exist yet.
3. Confirm the detected participant ID column.
4. Save or merge only after the preview is correct.
5. Switch to the **Survey** workflow.
6. Load `wellbeing.xlsx`.
7. Confirm the item columns and preview.
8. Save the converted result.
9. Open **Validator** and run a full check.

Expected outcome:

- participant files at project root
- survey files in subject folders
- a project that is ready for metadata completion and validation

## Common failure modes

### Wrong ID column selected

This is one of the most damaging import mistakes because everything downstream
depends on stable participant IDs.

Stop and fix this before saving.

### Preview looks incomplete or wrong

Do not treat preview as an optional extra step. If the preview is wrong, the save
result will usually be wrong too.

### Switching project mid-workflow

If you change projects, re-check the active project and re-run the preview before
saving. Do not assume stale selections still point at the new project context.

### Mixing participants cases

Do not use Case 1, Case 2, and Case 3 as interchangeable buttons. They are
different workflows with different safety expectations.

## When to move on to validation

Move to [VALIDATOR.md](VALIDATOR.md) when:

- the previewed result matches the source intent
- the files were saved into the correct project
- the import phase is complete for the current data slice

## Related pages

- [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md)
- [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- [VALIDATOR.md](VALIDATOR.md)
- [PROJECTS.md](PROJECTS.md)