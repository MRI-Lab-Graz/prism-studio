# Participant Mapping Guide

## Overview

The **Participant Mapping** feature allows you to automatically map unused survey columns (especially demographic data) to the `participants.tsv` file in your PRISM dataset.

## Key Differences

### 🆔 ID Mapping (`id_mapping.tsv`)
- **Purpose:** Maps participant IDs between different systems (e.g., LimeSurvey ID → local ID)
- **Created:** When you have different participant ID schemes
- **Format:** Two-column TSV file with source and target IDs

### 📋 Participant Mapping (`participants_mapping.json`)
- **Purpose:** Maps demographic and unused columns from survey data to `participants.tsv`
- **Created:** To include demographic variables in the participant dataset
- **Format:** Simple JSON file with source → target column mappings

## How to Create Participant Mapping

### Step 1: Run Dry-Run Preview

1. Go to **Survey Converter** tab
2. Upload your survey file (Excel, CSV, or LSA)
3. Click **Preview (Dry-Run)**
4. Review the output including **"UNUSED COLUMNS"** section

### Step 2: Create Mapping

Once you see unused columns in the preview:

1. Click **"Create Participant Mapping"** button (becomes enabled if unused columns exist)
2. A modal dialog appears showing all unused columns with their descriptions
3. **Select the columns** you want to include in participants.tsv
   - ✓ Demographic fields like age, sex, education are typically included
   - ✓ Pay attention to the descriptions to identify important columns
   - ✗ Skip system/internal columns

### Step 3: Save Mapping

1. Click **"Save Mapping"** button
2. The file `participants_mapping.json` is created in your survey library directory
3. Confirmation message shows the file location

## Example Mapping File

The generated `participants_mapping.json` looks like:

```json
{
  "age": "age",
  "sex": "sex_at_birth",
  "education": "education_level",
  "height": "height",
  "_569818X43539X590126": "participant_code"
}
```

**Structure:**
- **Key** (left): Source column name from your survey
- **Value** (right): Target column name in `participants.tsv` (should match your `survey-participant.json` template)

## For LimeSurvey Users

When using LimeSurvey (.lsa) files, cryptic field codes like `_569818X43540X590127` are automatically decoded to human-readable descriptions:

```
Field code: _569818X43540X590127
  → age
```

This makes it easy to identify which columns to map!

## Next Steps

After creating `participants_mapping.json`:

1. Run **Convert** to apply the mapping
2. The new columns will be added to `participants.tsv`
3. All participant data will be populated according to your mapping

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Create Participant Mapping" button is disabled | Run preview first, then ensure there are unused columns |
| Mapping file not created | Check that library path is valid and accessible |
| Wrong column names in mapping | Edit `participants_mapping.json` manually in your survey library directory |

## File Location

Your `participants_mapping.json` should be located in:

```
/path/to/project/code/library/survey/participants_mapping.json
```

It will be automatically detected when you run the converter.
