# Converter

Import data from various formats into PRISM/BIDS structure.

```{note}
This page is under construction. For now, see [Studio Overview](STUDIO_OVERVIEW.md) for converter basics.
```

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| **Excel** | `.xlsx`, `.xls` | Multiple sheets supported |
| **CSV** | `.csv` | Comma-separated values |
| **TSV** | `.tsv` | Tab-separated values |
| **SPSS** | `.sav` | With value labels preserved |
| **LimeSurvey** | `.csv` | Special handling for LS exports |

## Conversion Workflow

### 1. Select Source File

- Click **Browse** or drag-and-drop your file
- PRISM auto-detects the format and delimiter

### 2. Preview Data

- Review detected columns
- Check first few rows for correctness
- Adjust delimiter if needed (CSV/TSV)

### 3. Map Columns

**Required**:
- **Participant ID Column**: Which column contains subject IDs

**Optional**:
- **Session Column**: For multi-session studies
- **Task Name**: Label for this data (e.g., "depression", "anxiety")

### 4. Select Variables

Choose which columns to include in the output:
- Survey items
- Demographic variables
- Timestamps

### 5. Convert

Click **Convert** to generate:
- BIDS-structured TSV files (`sub-XXX_task-YYY_survey.tsv`)
- JSON sidecar files with metadata

### 6. Save to Project

If you have a project loaded:
- Click **Save to Project**
- Files are copied to `rawdata/sub-XXX/survey/`

## Output Structure

For a source file with participants sub-001 and sub-002:

```
rawdata/
├── sub-001/
│   └── survey/
│       ├── sub-001_task-depression_survey.tsv
│       └── sub-001_task-depression_survey.json
└── sub-002/
    └── survey/
        ├── sub-002_task-depression_survey.tsv
        └── sub-002_task-depression_survey.json
```

## LimeSurvey Import

LimeSurvey exports require special handling:

1. Export from LimeSurvey as **CSV with codes**
2. Load in Converter
3. PRISM automatically:
   - Parses question groups
   - Extracts response codes
   - Generates metadata from survey structure

→ See [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) for details.

## Participants Mapping

For demographic data with custom encodings:

→ See [Participants Mapping](PARTICIPANTS_MAPPING.md)
