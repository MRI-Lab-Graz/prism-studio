# Template Validation Implementation Summary

## Overview
I've successfully added comprehensive template validation support to PRISM. This allows you to validate survey and biometrics JSON templates before using them in your projects.

## What Was Added

### 1. Core Validation Module
**File**: `app/src/template_validator.py`

A new module that provides:
- **TemplateValidator class**: Core validation engine
- **TemplateValidationError class**: Structured error representation
- **validate_templates() function**: Convenient API for quick validation

The validator checks:
- ✅ Valid JSON structure
- ✅ Required Study metadata
- ✅ Item definitions with Description
- ✅ Internationalization (i18n) consistency
- ✅ Field formats (DOI, Year, language codes)
- ✅ Data types and enums

### 2. CLI Integration
**File**: `app/prism.py` (modified)

Added `--validate-templates` command:

```bash
# Validate a template library
python app/prism.py --validate-templates /path/to/library

# Example with official library
python app/prism.py --validate-templates official/library/survey
```

**Output includes**:
- File count and valid/error breakdown
- Detailed error messages grouped by severity
- Item-specific issues when applicable
- Exit code 1 on errors, 0 on success (CI/CD friendly)

### 3. Documentation
**File**: `docs/TEMPLATE_VALIDATION.md`

Comprehensive guide covering:
- What template validation does
- Template structure requirements
- Field reference (required & optional)
- Validation rules with examples
- Python API usage
- Best practices
- Troubleshooting

### 4. CLI Reference Update
**File**: `docs/CLI_REFERENCE.md` (modified)

Added `--validate-templates` to the options table and examples.

## Key Features

### Comprehensive Checks

```json
{
  "Study": {
    "OriginalName": "Required",    // ✅ Must exist
    "Authors": ["name"],           // Optional but recommended
    "Year": 2020,                  // ✅ Validated (1900-2100)
    "DOI": "10.xxxx/...",         // ✅ Format validated
    "License": {
      "en": "...",                 // ✅ Language keys validated
      "de": "..."
    }
  },
  "ITEM01": {
    "Description": "...",          // ✅ Required
    "Levels": {                    // ✅ Structure validated
      "1": "Label"
    }
  }
}
```

### Multiple Validation Levels

- **ERROR**: Critical issues that prevent template use
- **WARNING**: Issues that might affect functionality
- **INFO**: Informational messages

### Flexible Item Structure

Supports both formats:
```json
// Flat structure
{ "Study": {...}, "ITEM01": {...} }

// Nested structure
{ "Study": {...}, "Questions": { "ITEM01": {...} } }
```

### Metadata-Only Templates

Valid templates can contain just Study metadata without items:
```json
{
  "Study": {
    "OriginalName": "Instrument Name"
  }
}
```

## Usage Examples

### Command Line

```bash
# Basic validation
python app/prism.py --validate-templates /code/library/survey

# Exit code check in scripts
if ! python app/prism.py --validate-templates lib; then
  echo "Templates have errors"
  exit 1
fi
```

### Python API

```python
from template_validator import validate_templates, TemplateValidator

# Quick validation
errors, summary = validate_templates('/path/to/library')
print(f"Found {summary['total_errors']} errors")

# Detailed validation
validator = TemplateValidator('/path/to/library')
errors, summary = validator.validate_directory()

# Access error details
for error in errors:
    print(f"{error.file}: {error.message}")
    if error.item:
        print(f"  Item: {error.item}")
    if error.details:
        print(f"  Details: {error.details}")
```

## Validation Rules

### Study Metadata
- **OriginalName** (required): Must be non-empty
- **Year**: Must be integer between 1900-2100
- **DOI**: Must start with "10." or "https://doi.org/"
- **License/OriginalName** (if object): Must have "en" key

### Items
- **Description** (required): Must be non-empty
- **Reversed**: Must be boolean if present
- **Levels**: Must be object with appropriate structure
- **Internationalization**: English ("en") keys are minimum requirement

## Integration with PRISM

Template validation is **independent** from dataset validation:

```bash
# 1. Validate templates first
python app/prism.py --validate-templates /code/library/survey

# 2. Then validate dataset using those templates
python app/prism.py /code/my-study --library /code/library
```

## Testing

The implementation was tested with:
- ✅ Official library (110 valid templates)
- ✅ Invalid test cases (missing fields, wrong types)
- ✅ Python API
- ✅ CLI with both success and error cases
- ✅ Exit codes for CI/CD integration

## Files Modified/Created

| File | Change |
|------|--------|
| `app/src/template_validator.py` | **NEW** - Core validation engine |
| `app/prism.py` | Modified - Added `--validate-templates` option |
| `docs/TEMPLATE_VALIDATION.md` | **NEW** - Comprehensive user guide |
| `docs/CLI_REFERENCE.md` | Modified - Added command documentation |

## Next Steps

You can now:

1. **Validate your project templates**:
   ```bash
   cd /Users/karl/work/github/prism-studio
   source .venv/bin/activate
   python app/prism.py --validate-templates /code/library/survey
   ```

2. **Reference the documentation**:
   - [docs/TEMPLATE_VALIDATION.md](../docs/TEMPLATE_VALIDATION.md) for detailed guide
   - [docs/CLI_REFERENCE.md](../docs/CLI_REFERENCE.md) for CLI options

3. **Integrate with CI/CD**:
   ```yaml
   - name: Validate templates
     run: python app/prism.py --validate-templates library/
   ```

4. **Use the Python API** in your own scripts:
   ```python
   from template_validator import validate_templates
   errors, summary = validate_templates('library/')
   ```

## Architecture

The validator is designed to be:
- **Modular**: Can be used independently or with PRISM dataset validation
- **Extensible**: Easy to subclass for custom validation rules
- **Machine-friendly**: Structured errors, exit codes, API access
- **Human-friendly**: Clear error messages, verbose reporting

All code follows the project conventions and is integrated with the existing validator infrastructure.
