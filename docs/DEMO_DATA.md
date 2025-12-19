# Demo Data Guide

This document provides a comprehensive guide to the demo data included with PRISM. The demo folder contains synthetic data designed to help you learn PRISM workflows, test validation, and understand how to structure your own datasets.

## Overview

The `demo/` folder demonstrates the complete PRISM ecosystem:

| Component | Purpose |
|-----------|---------|
| `templates/` | Multilingual JSON sidecars (survey, biometrics) |
| `raw_data/` | Example source files + bad examples for testing |
| `derivatives/` | Scoring recipes for computed measures |
| `prism_structure_example/` | Correctly organized PRISM dataset |
| `flat_structure_example/` | Common disorganized format (for comparison) |

---

## Templates: Multilingual Survey & Biometrics

### Location
```
demo/templates/
├── participants.json          # Participant variable definitions
├── survey/
│   └── survey-wellbeing.json  # Well-being questionnaire (DE/EN)
└── biometrics/
    └── biometrics-fitness.json  # Fitness assessment (DE/EN)
```

### The Well-Being Survey (`survey-wellbeing.json`)

A 5-item synthetic questionnaire measuring general well-being:

| Item | English Description | German Description | Scale |
|------|--------------------|--------------------|-------|
| WB01 | Life satisfaction | Lebenszufriedenheit | 1-5 |
| WB02 | Happiness frequency | Häufigkeit von Glück | 1-5 |
| WB03 | Stress level (reverse) | Stressniveau (umgekehrt) | 1-5 |
| WB04 | Energy level | Energieniveau | 1-5 |
| WB05 | Sleep quality satisfaction | Schlafqualität | 1-5 |

**Scale anchors (example for WB01):**
- 1 = Not at all satisfied / Überhaupt nicht zufrieden
- 2 = Slightly satisfied / Wenig zufrieden
- 3 = Moderately satisfied / Mäßig zufrieden
- 4 = Very satisfied / Sehr zufrieden
- 5 = Extremely satisfied / Äußerst zufrieden

### I18n Structure

PRISM templates store **both languages in a single file** using nested objects:

```json
{
  "Study": {
    "TaskName": "wellbeing",
    "OriginalName": {
      "de": "Wohlbefindens-Kurzskala",
      "en": "Well-Being Short Scale"
    },
    "Description": {
      "de": "5-Item Fragebogen zur Erfassung des allgemeinen Wohlbefindens",
      "en": "5-item questionnaire measuring general well-being"
    }
  },
  "I18n": {
    "Languages": ["de", "en"],
    "DefaultLanguage": "en"
  },
  "WB01": {
    "Description": {
      "de": "Wie zufrieden sind Sie im Allgemeinen mit Ihrem Leben?",
      "en": "In general, how satisfied are you with your life?"
    },
    "Levels": {
      "1": {
        "de": "Überhaupt nicht zufrieden",
        "en": "Not at all satisfied"
      },
      "5": {
        "de": "Äußerst zufrieden",
        "en": "Extremely satisfied"
      }
    }
  }
}
```

**Benefits:**
- Single source of truth for translations
- No sync issues between separate files
- Compile to target language at export time

### Compiling to Single Language

```bash
# Extract German version
python prism_tools.py library-compile demo/templates/survey/survey-wellbeing.json --lang de

# Extract English version
python prism_tools.py library-compile demo/templates/survey/survey-wellbeing.json --lang en
```

---

## Raw Data: Source Files

### Location
```
demo/raw_data/
├── survey_wellbeing_data.tsv      # Valid survey responses
├── biometrics_fitness_data.tsv    # Valid biometrics data
└── bad_examples/                  # 13 intentionally broken files
```

### Valid Survey Data (`survey_wellbeing_data.tsv`)

10 synthetic participants with complete responses:

```tsv
participant_id  session   age  sex  education  handedness  WB01  WB02  WB03  WB04  WB05  completion_date
DEMO001         baseline  28   f    4          r           4     4     2     3     4     2025-01-15
DEMO002         baseline  34   m    5          r           3     3     3     3     3     2025-01-16
DEMO003         baseline  22   f    3          r           5     5     1     5     5     2025-01-17
...
```

**Column descriptions:**
- `participant_id`: Unique identifier (converted to `sub-DEMO001` format)
- `session`: Data collection session (becomes `ses-baseline`)
- `age`, `sex`, `education`, `handedness`: Demographic variables
- `WB01-WB05`: Survey item responses (1-5 Likert scale)
- `completion_date`: When the survey was completed

### Bad Examples for Testing

The `bad_examples/` folder contains 13 intentionally malformed files to test error handling:

| File | Issue | Expected Error |
|------|-------|----------------|
| `01_missing_id_column.tsv` | No participant_id column | Cannot identify participants |
| `02_wrong_delimiter.tsv` | Semicolons instead of tabs | Column parsing failure |
| `03_string_values.tsv` | "very high" instead of 5 | Non-numeric data error |
| `04_out_of_range_values.tsv` | Values like 99, -5, 300 | Out of range warning |
| `05_empty_values.tsv` | Missing cells | Missing value handling |
| `06_unknown_columns.tsv` | Extra columns not in template | Unknown column warning |
| `07_duplicate_ids.tsv` | Same participant twice | Duplicate entry warning |
| `08_inconsistent_columns.tsv` | Varying column counts | Parsing error |
| `09_mixed_types.tsv` | Mix of numbers, N/A, NULL, #REF! | Type validation errors |
| `10_empty_file.tsv` | Completely empty | No data error |
| `11_headers_only.tsv` | Headers but no rows | No participant data |
| `12_special_characters.tsv` | HTML tags, quotes | Sanitization test |
| `13_wrong_id_format.tsv` | IDs not in sub-XXX format | Format warning |

**Usage:**
```bash
# Test error handling via CLI
python prism_tools.py survey-convert \
    demo/raw_data/bad_examples/04_out_of_range_values.tsv \
    --library demo/templates \
    --output /tmp/test_output

# Or use the web interface Data Conversion page
```

---

## Derivatives: Scoring Recipes

### Location
```
demo/derivatives/
├── README.md
├── surveys/
│   └── wellbeing.json    # Wellbeing subscales & reverse coding
└── biometrics/
    └── fitness.json      # Fitness composite scores
```

### Wellbeing Scoring Recipe (`wellbeing.json`)

Computes derived scores from raw survey items:

```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": {
    "Name": "Well-Being Short Scale",
    "TaskName": "wellbeing"
  },
  "Transforms": {
    "Invert": {
      "Scale": {"min": 1, "max": 5},
      "Items": ["WB03"]
    }
  },
  "Scores": [
    {
      "Name": "WB_total",
      "Description": "Total Well-Being Score",
      "Method": "sum",
      "Items": ["WB01", "WB02", "WB03", "WB04", "WB05"],
      "Range": {"min": 5, "max": 25},
      "Interpretation": {
        "5-10": "Low well-being",
        "11-17": "Moderate well-being",
        "18-25": "High well-being"
      }
    },
    {
      "Name": "WB_positive",
      "Description": "Positive Affect Subscale",
      "Method": "mean",
      "Items": ["WB02", "WB04"]
    },
    {
      "Name": "WB_satisfaction",
      "Description": "Life Satisfaction Subscale",
      "Method": "mean",
      "Items": ["WB01", "WB05"]
    }
  ]
}
```

**Key features:**
- **Reverse coding**: WB03 (stress) is inverted so higher = better
- **Subscales**: Total, Positive Affect, Life Satisfaction
- **Methods**: `sum` or `mean` aggregation
- **Missing data**: `ignore` skips missing values

### Computing Derivatives

```bash
# Generate scored output from a PRISM dataset
python prism_tools.py derivatives-surveys /path/to/dataset \
    --recipe demo/derivatives/surveys/wellbeing.json \
    --output derivatives/

# Outputs: CSV, Excel (with codebook), and optional SPSS format
```

---

## PRISM Structure Example

### Location
```
demo/prism_structure_example/
├── .bidsignore
├── dataset_description.json
├── participants.json
├── participants.tsv
├── sub-001/
│   ├── eyetrack/
│   │   ├── sub-001_task-reading_eyetrack.tsv.gz
│   │   └── sub-001_task-reading_eyetrack.json
│   └── physio/
│       ├── sub-001_task-rest_physio.tsv.gz
│       └── sub-001_task-rest_physio.json
└── sub-002/
    ├── eyetrack/
    │   └── ...
    └── physio/
        └── ...
```

This is a **correctly organized** PRISM dataset demonstrating:

### Dataset-Level Files

**`dataset_description.json`** - Required metadata:
```json
{
  "Name": "PRISM Demo Dataset",
  "BIDSVersion": "1.8.0",
  "DatasetType": "raw",
  "License": "CC0",
  "Authors": ["Demo Author"],
  "Acknowledgements": "Synthetic demo data for PRISM testing"
}
```

**`participants.tsv`** - Participant demographics:
```tsv
participant_id  age  sex  handedness
sub-001         28   F    R
sub-002         34   M    R
```

**`participants.json`** - Variable definitions:
```json
{
  "age": {
    "Description": "Age of participant in years",
    "Units": "years"
  },
  "sex": {
    "Description": "Biological sex",
    "Levels": {
      "F": "Female",
      "M": "Male"
    }
  }
}
```

### Subject-Level Structure

Each subject folder contains modality subfolders:

- **`eyetrack/`** - Eye tracking data
- **`physio/`** - Physiological recordings (ECG, EDA, etc.)

**Naming convention:**
```
sub-<id>_[ses-<session>_]task-<task>_<modality>.<ext>
```

Examples:
- `sub-001_task-reading_eyetrack.tsv.gz`
- `sub-001_task-rest_physio.tsv.gz`

Each data file has a corresponding `.json` sidecar with metadata.

### Validating the Example

```bash
# Should pass with no errors
python prism.py demo/prism_structure_example/

# Output:
# ✓ Dataset validation complete
# 0 errors, 0 warnings
```

---

## Flat Structure Example (Anti-Pattern)

### Location
```
demo/flat_structure_example/
├── README.md
└── [messy files with inconsistent naming]
```

This folder demonstrates how data often arrives from experiments:
- No standardized naming
- Mixed file formats
- No metadata sidecars
- No participant organization

**Purpose:** Compare with `prism_structure_example/` to understand why standardization matters.

```bash
# Will show many validation errors
python prism.py demo/flat_structure_example/
```

---

## Hands-On Tutorials

### Tutorial 1: Validate Demo Dataset

```bash
# Activate environment
source .venv/bin/activate

# Validate the well-organized example
python prism.py demo/prism_structure_example/
# → Should pass

# Try the flat structure
python prism.py demo/flat_structure_example/
# → Will show errors
```

### Tutorial 2: Convert Survey Data

```bash
# Convert raw survey data to PRISM format
python prism_tools.py survey-convert \
    demo/raw_data/survey_wellbeing_data.tsv \
    --library demo/templates \
    --output /tmp/converted_survey \
    --force

# Validate the result
python prism.py /tmp/converted_survey
```

### Tutorial 3: Compute Derivatives

```bash
# After converting, compute subscale scores
python prism_tools.py derivatives-surveys /tmp/converted_survey \
    --recipe demo/derivatives/surveys/wellbeing.json \
    --output /tmp/converted_survey/derivatives

# Check the output
ls /tmp/converted_survey/derivatives/surveys/
# → wellbeing_scores.csv, wellbeing_scores.xlsx, codebook.json
```

### Tutorial 4: Test Error Handling

```bash
# Try importing a bad file
python prism_tools.py survey-convert \
    demo/raw_data/bad_examples/04_out_of_range_values.tsv \
    --library demo/templates \
    --output /tmp/bad_test

# Should produce clear error about values outside 1-5 range
```

### Tutorial 5: Web Interface

1. Start: `python prism-studio.py`
2. Open: http://localhost:5001
3. Go to **Validate** tab
4. Upload `demo/prism_structure_example/` → should pass
5. Go to **Data Conversion** tab
6. Select library: `demo/templates`
7. Upload `demo/raw_data/survey_wellbeing_data.tsv`
8. Watch real-time conversion log

---

## Summary

| Demo Component | What It Teaches |
|----------------|-----------------|
| `templates/survey/` | Multilingual JSON sidecar format |
| `templates/participants.json` | Participant variable definitions |
| `raw_data/survey_*.tsv` | Typical source data format |
| `raw_data/bad_examples/` | Error handling & validation |
| `derivatives/surveys/` | Scoring recipe format |
| `prism_structure_example/` | Correct PRISM organization |
| `flat_structure_example/` | Why standardization matters |

All demo data is **completely synthetic** and safe to share, modify, or use for testing.
