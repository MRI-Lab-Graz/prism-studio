# Converter - Participants Mapping Information Panel

This HTML/template snippet provides information about participants_mapping.json in the web converter interface.

## What is participants_mapping.json?

A `participants_mapping.json` file documents how to transform raw demographic data with custom encodings into PRISM standard format.

**Example:**
- Raw data: `sex: 1, 2, 4`
- Mapping specifies: `1→M, 2→F, 4→O`
- Output: Standardized `sex: M, F, O`

## Where to Place It

In your project structure:
```
my_dataset/
├── code/
│   └── library/
│       └── participants_mapping.json    ← PUT IT HERE
└── ...
```

Or alternatively:
```
my_dataset/
├── sourcedata/
│   └── participants_mapping.json        ← OR HERE
└── ...
```

## How It Works

1. **Create** `participants_mapping.json` in `code/library/`
2. **Specify** your demographic variable mappings
3. **Run validation** - mapping auto-applies
4. **Output**: Standardized `participants.tsv` generated automatically

## Mapping File Format

```json
{
  "version": "1.0",
  "description": "Your mapping description",
  "mappings": {
    "demographic_variable": {
      "source_column": "raw_column_name",
      "standard_variable": "prism_variable_name",
      "type": "string|integer|float",
      "value_mapping": {
        "raw_value": "standard_value"
      }
    }
  }
}
```

## Example

**Raw data** (wellbeing.tsv):
```
participant_id   sex   education   handedness
DEMO001          2     4           1
DEMO002          1     5           1
```

**Mapping** (participants_mapping.json):
```json
{
  "mappings": {
    "sex": {
      "source_column": "sex",
      "standard_variable": "sex",
      "value_mapping": {
        "1": "M",
        "2": "F",
        "4": "O"
      }
    },
    "handedness": {
      "source_column": "handedness",
      "standard_variable": "handedness",
      "value_mapping": {
        "1": "R",
        "2": "L"
      }
    }
  }
}
```

**Output** (participants.tsv):
```
participant_id   sex   education_level   handedness
DEMO001          F     4                 R
DEMO002          M     5                 R
```

## Features

✓ **Auto-detection** - PRISM finds and applies mapping automatically  
✓ **Value transformation** - Maps numeric codes to standard codes  
✓ **Column renaming** - Can rename columns during import  
✓ **Validation** - Checks specification syntax  
✓ **Logging** - Shows progress in web terminal  
✓ **Non-breaking** - Optional (works without it)  

## Standard PRISM Variables

Common demographic variables:
- `participant_id` - Participant identifier
- `age` - Age in years
- `sex` - Biological sex (M, F, O, n/a)
- `gender` - Gender identity
- `education_level` - Education level (ISCED)
- `education_years` - Years of education
- `handedness` - Hand dominance (R, L, A, n/a)
- `group` - Study group assignment
- `smoking_status`, `alcohol_consumption`, `physical_activity`

See `official/participants.json` for complete reference.

## Learning Resources

- **Quick Guide**: `docs/PARTICIPANTS_MAPPING.md`
- **Implementation**: `docs/PARTICIPANTS_MAPPING_IMPLEMENTATION.md`
- **Workshop Exercise**: `examples/workshop/exercise_2_participant_mapping/`
- **Example Mapping**: `examples/workshop/exercise_1_raw_data/code/library/participants_mapping.json`

## Getting Help

If you encounter issues:
1. Check that the file is in `code/library/` (not `rawdata/`)
2. Verify JSON syntax (use online JSON validator)
3. Ensure source column names match raw data exactly (case-sensitive!)
4. Check that all possible values are in the `value_mapping`
5. See `docs/PARTICIPANTS_MAPPING.md#troubleshooting`

