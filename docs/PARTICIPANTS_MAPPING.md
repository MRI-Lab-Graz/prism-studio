# Participant Variable Mapping Guide

## Overview

When importing raw participant data into PRISM, your source files (e.g., `wellbeing.tsv`, `fitness_data.tsv`) may use custom encodings for demographic variables (numeric codes, different column names, etc.) that don't match the standardized PRISM schema.

The **`participants_mapping.json`** file allows you to:
1. **Specify** which columns in your raw data represent participant demographics
2. **Map** those columns to standardized PRISM variable names
3. **Transform** numeric codes (e.g., 1, 2, 4) to standard codes (e.g., M, F, O)
4. **Auto-convert** participant data during dataset validation

---

## Quick Start

### Step 1: Create the mapping file

Place a `participants_mapping.json` file in your project's **code/library/** directory:

```
my_dataset/
├── code/
│   └── library/
│       └── participants_mapping.json    ← PUT IT HERE
├── sourcedata/
│   └── raw_data/
│       ├── wellbeing.tsv
│       └── fitness_data.tsv
├── dataset_description.json
├── participants.tsv
├── sub-001/
│   └── ...
└── ...
```

Alternatively, you can place it in **sourcedata/** if that's more convenient for your workflow:

```
my_dataset/
├── sourcedata/
│   ├── participants_mapping.json        ← OR HERE
│   └── raw_data/
│       └── wellbeing.tsv
└── ...
```

### Step 2: Define your mappings

```json
{
  "version": "1.0",
  "description": "Mapping for our study participant data",
  "mappings": {
    "participant_id": {
      "source_column": "participant_id",
      "standard_variable": "participant_id",
      "type": "string"
    },
    "sex": {
      "source_column": "sex",
      "standard_variable": "sex",
      "type": "string",
      "value_mapping": {
        "1": "M",
        "2": "F",
        "4": "O"
      }
    }
  }
}
```

### Step 3: Run conversion

When you validate or convert your dataset, PRISM will:
- ✓ Auto-detect the `participants_mapping.json` file
- ✓ Apply transformations (numeric → standard codes)
- ✓ Generate `participants.tsv` with standardized values
- ✓ Log all transformations to the web terminal

---

## Complete Example: Wellbeing Survey

**Source data** (`raw_data/wellbeing.tsv`):
```
participant_id   session   age   sex   education   handedness   WB01   ...
DEMO001          baseline  28    2     4           1            4      ...
DEMO002          baseline  34    1     5           1            3      ...
```

**Mapping file** (`participants_mapping.json`):
```json
{
  "version": "1.0",
  "description": "Mapping for wellbeing survey raw data to PRISM standard",
  "source_file": "raw_data/wellbeing.tsv",
  "mappings": {
    "participant_id": {
      "source_column": "participant_id",
      "standard_variable": "participant_id",
      "type": "string",
      "description": "Unique participant identifier"
    },
    "age": {
      "source_column": "age",
      "standard_variable": "age",
      "type": "integer",
      "units": "years",
      "description": "Age in years"
    },
    "sex": {
      "source_column": "sex",
      "standard_variable": "sex",
      "type": "string",
      "value_mapping": {
        "1": "M",
        "2": "F",
        "4": "O"
      },
      "description": "Biological sex: 1=M, 2=F, 4=O"
    },
    "education": {
      "source_column": "education",
      "standard_variable": "education_level",
      "type": "string",
      "value_mapping": {
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "5": "5",
        "6": "6"
      },
      "description": "ISCED 2011 level"
    },
    "handedness": {
      "source_column": "handedness",
      "standard_variable": "handedness",
      "type": "string",
      "value_mapping": {
        "1": "R",
        "2": "L"
      },
      "description": "Hand preference: 1=R, 2=L"
    }
  }
}
```

**Output** (`participants.tsv`):
```
participant_id   age   sex   education_level   handedness
DEMO001          28    F     4                 R
DEMO002          34    M     5                 R
```

✓ Numeric codes automatically converted to standard codes!

---

## Mapping Specification Format

### Root level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Version of the mapping schema (e.g., "1.0") |
| `description` | string | No | Human-readable description of this mapping |
| `source_file` | string | No | Path to the source file this mapping applies to |
| `instructions` | object | No | Custom instructions for users |
| `mappings` | object | Yes | Dictionary of column mappings |

### Per-column mapping

Each entry in `mappings` object:

```json
{
  "my_mapping_name": {
    "source_column": "column_name_in_raw_data",
    "standard_variable": "standardized_variable_name",
    "type": "string|integer|float",
    "units": "years|cm|kg|...",
    "value_mapping": {
      "raw_value": "standard_value",
      "1": "M",
      "2": "F"
    },
    "description": "What this variable represents"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_column` | string | Yes | Column name in the raw TSV file |
| `standard_variable` | string | Yes | Name of the standardized variable (from `participants.json` schema) |
| `type` | string | Yes | Data type: `string`, `integer`, `float` |
| `units` | string | No | Unit of measurement (e.g., "years", "cm") |
| `value_mapping` | object | No | Maps source values to standard values (for recoding) |
| `description` | string | No | Explanation of the variable |

---

## Standard PRISM Participant Variables

These are the standard variable names recognized by PRISM:

### Core Demographics
- `participant_id` - Unique identifier
- `age` - Age in years
- `sex` - Biological sex (M, F, O, n/a)
- `gender` - Gender identity

### Education & Employment
- `education_level` - ISCED 2011 (0-8, n/a)
- `education_years` - Years of formal education
- `employment_status` - Employment category

### Physical Traits
- `handedness` - Hand dominance (R, L, A, n/a)
- `height` - Height in cm
- `weight` - Weight in kg
- `bmi` - Body Mass Index

### Health & Lifestyle
- `smoking_status` - Smoking history
- `alcohol_consumption` - Alcohol use frequency
- `physical_activity` - Exercise frequency
- `medication_current` - Current medications (yes/no)

### Clinical
- `psychiatric_diagnosis` - Mental health diagnosis history
- `neurological_diagnosis` - Neurological condition history
- `vision` - Visual acuity status
- `hearing` - Hearing ability status

### Other
- `group` - Study group (control, patient, etc.)
- `marital_status` - Partnership status
- `native_language` - Language code (e.g., en, de)
- `country_of_birth` - ISO 3166-1 code (e.g., DE, US)
- `country_of_residence` - ISO 3166-1 code
- `ethnicity` - Ethnic background category
- `income_bracket` - Income range
- `residence_type` - Urban/suburban/rural

See `official/participants.json` in the PRISM repository for complete definitions and expected values.

---

## Value Mapping Reference

Common value mappings you might need:

### Sex / Gender
```json
"value_mapping": {
  "1": "M",
  "2": "F",
  "3": "O",
  "m": "M",
  "f": "F",
  "male": "M",
  "female": "F"
}
```

### Handedness
```json
"value_mapping": {
  "1": "R",
  "2": "L",
  "3": "A",
  "right": "R",
  "left": "L"
}
```

### Education Level (ISCED 2011)
```json
"value_mapping": {
  "1": "1",
  "2": "2",
  "3": "3",
  "4": "4",
  "5": "5",
  "6": "6",
  "7": "7",
  "8": "8"
}
```

### Yes/No fields
```json
"value_mapping": {
  "1": "yes",
  "0": "no",
  "yes": "yes",
  "no": "no",
  "y": "yes",
  "n": "no"
}
```

---

## Workflow Integration

### In the Web Interface

1. **Upload dataset folder**
2. PRISM detects `participants_mapping.json` at root
3. Shows: "Found participants mapping - Review transformations?"
4. Displays mapping summary and logs transformation
5. Auto-generates `participants.tsv` with standardized values

### In the CLI

```bash
python prism.py /path/to/my_dataset --apply-mapping
```

Or automatically applied during validation:
```bash
python prism.py /path/to/my_dataset
```

---

## File Location

The `participants_mapping.json` file should be placed in one of these **project infrastructure locations**:

1. **`code/library/participants_mapping.json`** (recommended)
   - Standard location for preprocessing specifications in PRISM/BIDS YODA layout
   - Part of the project's code/methodology
   - Not transferred to final dataset

2. **`sourcedata/participants_mapping.json`** (alternative)
   - Alternative location if raw data lives in sourcedata/
   - Clear association with raw data

**Why not in the dataset root?**
The mapping file is a **conversion specification**, not part of the final BIDS/PRISM dataset:
- It's used to transform raw data INTO standardized format
- Once data is imported into the dataset root structure, the mapping is no longer needed
- Keeping it in `code/` or `sourcedata/` makes this clear
- It's automatically excluded from BIDS validation

## BIDS Compatibility

The mapping file location (`code/`, `sourcedata/`) is standard for BIDS and automatically excluded from validation.

---

## Troubleshooting

### "No mapping found - continue without?"
- Place `participants_mapping.json` in the dataset root
- Check file name spelling (case-sensitive)
- Ensure valid JSON syntax

### "Source column 'X' not found"
- Verify column name in raw TSV file matches exactly
- Check for typos or whitespace
- Column names are case-sensitive

### "Values don't match mapping"
- Check numeric values (e.g., "1" vs 1)
- Include all expected values in `value_mapping`
- Use descriptive key names for troubleshooting

### "Mapping validation failed"
- Ensure `version` and `mappings` fields exist
- Check JSON syntax (use online JSON validator)
- Each mapping needs `source_column` and `standard_variable`

---

## Examples

### Example 1: Simple numeric sex coding

**Raw data:**
```
participant_id   sex
sub-001          1
sub-002          2
```

**Mapping:**
```json
{
  "mappings": {
    "sex": {
      "source_column": "sex",
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

**Output:**
```
participant_id   sex
sub-001          M
sub-002          F
```

### Example 2: Rename and recode education

**Raw data:**
```
participant_id   school_years
sub-001          12
sub-002          16
```

**Mapping:**
```json
{
  "mappings": {
    "education": {
      "source_column": "school_years",
      "standard_variable": "education_years",
      "type": "integer",
      "units": "years"
    }
  }
}
```

**Output:**
```
participant_id   education_years
sub-001          12
sub-002          16
```

### Example 3: Complex multipart mapping

**Raw data:**
```
participant_id   pid   visit   age_years   sex_code   handed
sub-001          P001  1       28          2          2
sub-002          P002  1       34          1          1
```

**Mapping:**
```json
{
  "mappings": {
    "participant_id": {
      "source_column": "pid",
      "standard_variable": "participant_id"
    },
    "session": {
      "source_column": "visit",
      "standard_variable": "session",
      "value_mapping": {
        "1": "baseline",
        "2": "followup"
      }
    },
    "age": {
      "source_column": "age_years",
      "standard_variable": "age",
      "type": "integer",
      "units": "years"
    },
    "sex": {
      "source_column": "sex_code",
      "standard_variable": "sex",
      "value_mapping": {
        "1": "M",
        "2": "F"
      }
    },
    "handedness": {
      "source_column": "handed",
      "standard_variable": "handedness",
      "value_mapping": {
        "1": "R",
        "2": "L"
      }
    }
  }
}
```

**Output:**
```
participant_id   session   age   sex   handedness
P001             baseline  28    F     L
P002             baseline  34    M     R
```

---

## Best Practices

1. **Document your encoding** - Always explain what numeric codes mean in the mapping
2. **Be consistent** - Use the same mapping across all files in a study
3. **Keep it simple** - Only map participant variables, not survey items
4. **Validate mappings** - Check for typos and missing value mappings
5. **Version control** - Commit `participants_mapping.json` to git with your dataset
6. **Test first** - Dry-run on a small dataset before full conversion

---

## Getting Help

- Check the examples in `examples/workshop/` 
- See `official/participants.json` for all standard variables and definitions
- Run with verbose logging to see transformation details
- Check `.prismrc.json` for validation settings

