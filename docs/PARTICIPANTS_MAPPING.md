# Sociodemographics Import

Use this page when you want to create, replace, review, or safely merge `participants.tsv` and `participants.json`.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## Where this happens

Open:

- PRISM Studio
- Converter
- Sociodemographics

This is the guided workflow for participant-level variables such as age, sex, gender, handedness, and education.

Studio now makes three cases explicit:

1. Case 1: Import file as source of truth
2. Case 2: Modify existing project files
3. Case 3: Safe merge from imported file

## What PRISM creates

The normal result is two files:

- `participants.tsv`
- `participants.json`

The TSV stores the values. The JSON stores the field descriptions and annotations.

## Recommended beginner workflow

1. Load your project first.
2. Open Converter and switch to Sociodemographics.
3. Pick the case that matches the current project state.
4. If you are using Case 1 or Case 3, choose the participant data file.
5. Review the detected fields or the existing project files.
6. Add more columns only if you need them.
7. Adjust metadata if needed.
8. Finish with the action that matches the active case.

This is safer than editing `participants.tsv` by hand.

## Studio case guide

Use the same case names that appear in Studio:

### Case 1: Import file as source of truth

Use this when you want one imported table to define the participant files.

- Create the first `participants.tsv` and `participants.json` for a project.
- Rebuild them from a cleaner source file.
- Replace existing participant files completely from a new import.

### Case 2: Modify existing project files

Use this when the project already has `participants.tsv` and you want to keep those files as the source of truth.

- Review the current `participants.tsv` and `participants.json`.
- Save metadata or NeuroBagel changes back into the project.
- Normalize or refresh the existing participant files in place.

This mode does not import a new source table.

### Case 3: Safe merge from imported file

Use this when the project already has `participants.tsv`, but you want to pull in missing values, new participants, or new columns from another source table without replacing the existing file.

## Step 1: Choose the participant data file

This step applies to Case 1 and Case 3.

Start with a table that contains one participant identifier column and the sociodemographic columns you want to keep.

Common examples are:

- Excel files
- CSV files
- TSV files

## Step 2: Check the ID column

PRISM tries to detect the source ID column automatically.

Always check it before continuing. The source ID column is renamed to `participant_id` in the output.

This step matters because everything else depends on stable participant IDs.

## Step 3: Review participant fields

Use the review step to confirm:

- the correct rows were loaded
- the ID column is correct
- the important sociodemographic columns are present
- the values look sensible

In Case 2, the review step shows the current project files instead of an imported source table.

Do this before creating files.

## Step 4: Add more columns if needed

Not every source column belongs in `participants.tsv`.

Keep the table focused. Add extra columns only when they are useful for documentation, analysis, or downstream metadata.

Good beginner choices are:

- age
- sex
- gender
- handedness
- education level

## Step 5: Adjust metadata

PRISM lets you review and adjust field descriptions before writing the files.

This is also the place where you may add optional NeuroBagel-style annotations.

You can save draft metadata if you want, but you do not have to. Current metadata edits are still used when you create the final participant files.

## Step 6: Save, replace, or apply

After the review looks correct, finish with the action that matches the active case.

- Case 1 writes new files or replaces existing files from the imported table.
- Case 2 saves the current project files in place.
- Case 3 applies the merge only after the preview shows zero blocking conflicts.

PRISM writes:

- `participants.tsv` at the project root
- `participants.json` at the project root

If files already exist, PRISM warns you before replacing them.

## Existing projects: choose the right case

There are three common situations:

1. No participant files exist yet.
2. `participants.tsv` already exists and you only want to improve metadata or add NeuroBagel annotations.
3. `participants.tsv` already exists and you want to merge new values from another source table.

These are different workflows and should not be treated the same way.

### Case 1: Import file as source of truth

If the project does not have participant files yet, create:

- `participants.tsv`
- `participants.json`

This is the standard beginner workflow described above.

If participant files already exist, the same case can still be used to replace them from a new import file.

### Case 2: Modify existing project files

If the values in `participants.tsv` are already the source of truth, use Case 2 to review and save the existing project files in place.

Typical reasons are:

- improve field descriptions
- add or refine NeuroBagel annotations
- normalize the existing `participants.tsv` and `participants.json` without importing a new file

Case 2 does not pull values from a new source table.

### Case 3: Safe merge from imported file

This is the risky case.

PRISM now treats merge as a preview-first workflow:

- first convert the source table to canonical participant columns,
- then compare it against the existing `participants.tsv`,
- then apply only if there are no unresolved conflicts.

## Safe merge rules

The merge workflow follows these rules:

- subjects are matched by canonical `participant_id` only
- no fuzzy matching is used
- overlapping columns are safe only when values are equal or the existing value is empty
- if the existing value is empty and the incoming value is present, PRISM fills the missing value
- if both existing and incoming values are non-empty and different, PRISM reports a conflict and blocks apply
- new participants are appended
- new columns are added to `participants.tsv`
- newly added columns are also added to `participants.json`
- applying a merge creates backups of the existing participant files first

This is stricter than the normal create workflow on purpose.

## Merge preview and apply from the CLI

Preview a merge:

```bash
/Users/karl/work/github/prism-studio/.venv/bin/python app/prism_tools.py participants merge \
  --input sourcedata/demographics.csv \
  --project /path/to/project \
  --json
```

Apply the merge only after the preview shows zero conflicts:

```bash
/Users/karl/work/github/prism-studio/.venv/bin/python app/prism_tools.py participants merge \
  --input sourcedata/demographics.csv \
  --project /path/to/project \
  --apply \
  --json
```

The preview reports:

- matched participants
- new participants
- existing-only participants
- new columns
- values that can safely fill blanks
- conflicts that must be resolved first

If conflicts are reported, do not apply the merge yet.

You can also export the full conflict report as CSV:

```bash
/Users/karl/work/github/prism-studio/.venv/bin/python app/prism_tools.py participants merge \
  --input sourcedata/demographics.csv \
  --project /path/to/project \
  --conflicts-csv
```

In PRISM Studio, the merge preview shows a "Download Full Conflict Report" button whenever blocking conflicts exist.

## About `participants_mapping.json`

PRISM can also use a `participants_mapping.json` file to map source columns to standard output names.

This is useful when your source table uses custom names or coded values.

Example uses:

- rename `pid` to `participant_id`
- map `sex_code` to `sex`
- convert `1` and `2` into `M` and `F`

## Supported mapping file locations

PRISM currently looks for `participants_mapping.json` in project-local locations such as:

- project root
- `code/`
- `code/library/`
- `code/library/survey/`

When the mapping is created from the Studio UI, the normal save target is `code/library/`.

## Minimal mapping example

```json
{
  "version": "1.0",
  "description": "Mapping for participant variables",
  "mappings": {
    "participant_id": {
      "source_column": "pid",
      "standard_variable": "participant_id",
      "type": "string"
    },
    "sex": {
      "source_column": "sex_code",
      "standard_variable": "sex",
      "type": "string",
      "value_mapping": {
        "1": "M",
        "2": "F"
      }
    }
  }
}
```

## Common beginner mistakes

- using the wrong ID column
- importing too many source columns into `participants.tsv`
- skipping the review step
- forgetting that `participant_id` is the required output name
- editing old metadata locally after the preview has already changed

## Useful standard variables

Common standardized variables include:

- `participant_id`
- `age`
- `sex`
- `gender`
- `handedness`
- `education_level`
- `education_years`

Keep the first version small. You can always add more fields later.

## Related pages

- Projects: [PROJECTS.md](PROJECTS.md)
- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)
- Template editing: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Recipe-based scoring: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- Analysis and export outputs: [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)