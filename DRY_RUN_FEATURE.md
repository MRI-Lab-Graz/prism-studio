# Dry-Run Preview Feature for Survey Conversion

## Overview

The dry-run feature allows you to preview what will happen during survey data conversion **before** actually creating any files. This helps you identify and fix data quality issues in your input data before the actual conversion.

## Why Use Dry-Run?

- **Identify data issues early**: See missing values, invalid entries, and out-of-range values
- **Preview file structure**: See exactly what files will be created
- **Check participant mapping**: Verify IDs are correctly normalized
- **Avoid wasted time**: Fix issues before running the full conversion
- **No file creation**: Preview mode doesn't write anything to disk

## Common Issues Detected

The dry-run preview will warn you about:

1. **Duplicate participant IDs** - Multiple rows with the same participant ID
2. **Unexpected values** - Values not matching the expected categorical levels
3. **Out-of-range values** - Numeric values outside the expected min/max range
4. **Missing data** - High percentages of missing responses per participant
5. **Invalid formatting** - Data that doesn't match the expected format

## How to Use

### CLI (Command Line)

```bash
# Run with --dry-run flag
python prism_tools.py survey convert \
  --input your_survey_data.lsa \
  --output ./output \
  --dry-run
```

The output will show:
- Summary of participants and tasks
- Data quality issues that need fixing
- Participant preview with completeness percentage
- Column mapping details
- Files that would be created

### Web Interface

1. Go to the **Converter** page
2. Upload your survey file (.lsa, .xlsx, .csv, .tsv)
3. Configure conversion settings (ID column, session, etc.)
4. Click **Preview (Dry-Run)** button instead of Convert
5. Review the output in the conversion log terminal
6. Fix any issues in your input data
7. Click **Convert** when ready

## Example Output

```
🔍 PREVIEW MODE (Dry-Run)
═══════════════════════════════════════
Analyzing file: survey_responses.lsa
No files will be created.

📊 SUMMARY
   Total participants: 120
   Unique participants: 118
   Tasks detected: phq9, gad7, panas
   Total files to create: 368

⚠️  DATA ISSUES FOUND (3)
   Fix these issues BEFORE conversion:

   [ERROR] duplicate_ids
   → Found 2 duplicate participant IDs after normalization
   → Duplicates: sub-001, sub-042

   [WARNING] unexpected_values
   → Column: PHQ9_1 (task: phq9, item: PHQ9_1)
   → Expected values: 0, 1, 2, 3
   → Unexpected values: 4, 99

👥 PARTICIPANT PREVIEW (first 10)
   ✓ sub-001 (ses-1)
      Raw ID: P001
      Completeness: 95.2% (40/42 items)
   
   ⚠ sub-002 (ses-1)
      Raw ID: P002
      Completeness: 71.4% (30/42 items)

📋 COLUMN MAPPING (first 15)
   ✓ PHQ9_1
      → Task: phq9, Item: PHQ9_1
      → Missing: 2.5% (3 values)
   
   ⚠ GAD7_1
      → Task: gad7, Item: GAD7_1
      → Missing: 5.0% (6 values)
      ⚠ Has unexpected values!

📁 FILES TO CREATE
   Metadata files: 3
   Sidecar files: 4
   Data files: 361

═══════════════════════════════════════
Preview complete. Run Convert to create files.
```

## Fixing Issues

### Duplicate IDs
Edit your input file to ensure each participant has a unique ID, or use the "Duplicate Handling" option:
- **Error** (default): Stop if duplicates found
- **Keep First**: Keep only the first occurrence
- **Keep Last**: Keep only the last occurrence  
- **Sessions**: Create multiple sessions (ses-1, ses-2, etc.)

### Unexpected Values
Check your input data for:
- Typos in response codes
- Data entry errors
- Values that should be marked as missing (use empty cells or "n/a")

### Out of Range Values
Verify that numeric responses are within the expected range for that questionnaire item.

## Best Practices

1. **Always run dry-run first** on new datasets
2. **Fix issues at the source** in your original data file
3. **Use strict levels validation** during preview to catch more issues
4. **Review completeness percentages** - low values may indicate data collection problems
5. **Check the column mapping** to ensure items are correctly matched to tasks

## Technical Details

The dry-run feature:
- Parses the input file completely
- Validates against survey templates
- Checks data quality and formatting
- Generates detailed preview information
- **Does NOT write any files** to disk
- Returns all issues in a structured format

## Related Documentation

- [Survey Conversion Documentation](docs/CONVERTER.md)
- [LimeSurvey Integration](docs/LIMESURVEY_INTEGRATION.md)
- [Error Codes Reference](docs/ERROR_CODES.md)
