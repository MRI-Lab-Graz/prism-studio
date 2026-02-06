# Participant Mapping Implementation - Summary

## ✅ Completed Implementation

A complete participant data converter has been implemented to handle custom demographic variable encodings.

### Components

#### 1. **ParticipantsConverter Class** (`src/participants_converter.py`)
- Auto-detects `participants_mapping.json` files
- Validates mapping specifications
- Converts raw participant data to standardized PRISM format
- Supports value mapping (numeric codes → standard codes)
- Generates template mappings from source files
- Comprehensive logging

**Key Methods:**
- `load_mapping_from_file(file_path)` - Load mapping from any location
- `validate_mapping(mapping)` - Validate specification
- `convert_participant_data(source_file, mapping)` - Transform data
- `create_mapping_template(source_file)` - Generate template from raw data

#### 2. **Web Integration** (`app/src/web/validation.py`)
- `_apply_participants_mapping()` function auto-detects and applies mapping during validation
- Searches for mapping in standard project locations
- Reports progress to web terminal
- Non-blocking (silently skips if mapping not found)

#### 3. **Mapping Specification Format**
```json
{
  "version": "1.0",
  "description": "Mapping description",
  "mappings": {
    "variable_name": {
      "source_column": "raw_column",
      "standard_variable": "prism_variable",
      "type": "string|integer|float",
      "units": "optional units",
      "value_mapping": {
        "raw_value": "standard_value"
      }
    }
  }
}
```

### File Locations

**Project Structure (YODA Layout):**
```
my_dataset/
├── code/
│   └── library/
│       └── participants_mapping.json    ← Mapping specification
├── sourcedata/
│   └── raw_data/
│       ├── wellbeing.tsv               ← Raw data with custom codes
│       └── fitness_data.tsv
├── rawdata/                            ← Final BIDS/PRISM dataset
│   ├── dataset_description.json
│   ├── participants.tsv                ← Generated from mapping
│   ├── participants.json
│   └── sub-*/
└── ...
```

**Why `code/library/`?**
- It's a **conversion specification**, not part of final dataset
- Standard BIDS/PRISM YODA layout location
- Automatically excluded from BIDS validation
- Clear separation: raw data → conversion specs → final dataset

### Example: Wellbeing Survey

**Workshop Example Location:**
`examples/workshop/exercise_1_raw_data/code/library/participants_mapping.json`

**Input** (`raw_data/wellbeing.tsv`):
```
participant_id   sex   education   handedness
DEMO001          2     4           1
DEMO002          1     5           1
```

**Mapping** (participants_mapping.json):
```json
{
  "sex": {
    "source_column": "sex",
    "standard_variable": "sex",
    "value_mapping": {
      "1": "M",
      "2": "F",
      "4": "O"
    }
  }
}
```

**Output** (participants.tsv):
```
participant_id   sex
DEMO001          F
DEMO002          M
```

### Integration Points

1. **During Validation** (`run_validation()`)
   - Auto-applies mapping before dataset validation
   - Logs transformation messages to progress callback
   - Generates `participants.tsv` with standardized values

2. **During Conversion**
   - Converter tools can import ParticipantsConverter directly
   - Use `apply_participants_mapping()` function

3. **Template Generation**
   - Users can auto-generate mapping template from raw data
   - Provides sample values and suggestions

### Testing

**Test Script:** `tests/test_participants_mapping.py`

Verifies:
- ✓ Mapping file loading
- ✓ Specification validation
- ✓ Value transformation (1→M, 2→F, etc.)
- ✓ Output file generation
- ✓ Template generation

**Result:** All tests pass ✓

### Documentation

**Guide:** `docs/PARTICIPANTS_MAPPING.md`

Includes:
- Quick start (5 minutes)
- Complete specification format reference
- Standard PRISM variables list
- Value mapping reference (common patterns)
- Workflow integration guide
- Troubleshooting section
- 5+ worked examples

### Standard Variables Supported

**Demographics:**
- participant_id, age, sex, gender, handedness

**Education/Employment:**
- education_level, education_years, employment_status

**Health/Lifestyle:**
- smoking_status, alcohol_consumption, physical_activity, medication_current

**Clinical:**
- psychiatric_diagnosis, neurological_diagnosis, vision, hearing

**Other:**
- marital_status, native_language, country_of_birth, income_bracket, group, etc.

See `official/participants.json` for complete definitions.

### Next Steps for Users

1. **Create mapping file** in `code/library/participants_mapping.json`
2. **Specify your raw data columns** and their PRISM equivalents
3. **Define value mappings** for numeric codes
4. **Run dataset validation** - mapping auto-applies during validation
5. **Verify output** - check generated `participants.tsv`

### Error Handling

- Missing mapping file → Skipped silently (not required)
- Invalid JSON → Logged warning, validation continues
- Source column not found → Warns and skips that mapping
- Unmapped values → Keeps original values, shows warning count
- Conversion errors → Non-blocking, partial data may be used

All errors are logged to web terminal for troubleshooting.

### Design Rationale

✅ **Transparent** - Mapping file documents the encoding  
✅ **Reusable** - Same mapping for all files in study  
✅ **Flexible** - Works with any column names/encodings  
✅ **Safe** - Non-breaking (existing workflows unaffected)  
✅ **BIDS-compatible** - Mapping in `code/`, not in `rawdata/`  
✅ **Discoverable** - Standard location in project structure  
✅ **Well-documented** - Comprehensive guide with examples  

