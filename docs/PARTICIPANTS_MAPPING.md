# Sociodemographics Import

Use this page when you want to create `participants.tsv` and `participants.json` from a source table.

This page is written for beginners. Use the written guide here for the full workflow. Use the companion videos for quick hands-on examples.

## Where this happens

Open:

- PRISM Studio
- Converter
- Sociodemographics

This is the guided workflow for participant-level variables such as age, sex, gender, handedness, and education.

## What PRISM creates

The normal result is two files:

- `participants.tsv`
- `participants.json`

The TSV stores the values. The JSON stores the field descriptions and annotations.

## Recommended beginner workflow

1. Load your project first.
2. Open Converter and switch to Sociodemographics.
3. Choose the participant data file.
4. Review the detected fields.
5. Add more columns only if you need them.
6. Adjust metadata if needed.
7. Create the participant files.

This is safer than editing `participants.tsv` by hand.

## Step 1: Choose the participant data file

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

## Step 6: Create participant files

After the review looks correct, create the files.

PRISM writes:

- `participants.tsv` at the project root
- `participants.json` at the project root

If files already exist, PRISM warns you before overwriting them.

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