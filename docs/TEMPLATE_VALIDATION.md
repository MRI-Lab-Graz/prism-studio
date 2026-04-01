# Template Validation

The PRISM template validator helps you ensure that survey and biometrics JSON templates are properly structured and valid. This is essential when preparing custom project templates or maintaining template libraries.

## What is Template Validation?

Template validation checks survey and biometrics JSON files for:

1. **Valid JSON Structure** - File must be parseable JSON
2. **Required Metadata** - Study section with essential information
3. **Item Structure** - Individual item definitions with proper fields
4. **Internationalization (i18n)** - Language codes and consistency
5. **Field Formats** - Years, DOIs, language codes follow proper formats

For survey templates, it helps to keep two cases separate:

- **Official library templates** in `official/library/survey/` describe the canonical instrument.
- **Project templates** in `code/library/survey/` describe the actual administration in that project.

Project templates are expected to complete administration-specific fields in `Technical`, especially `AdministrationMethod`, `SoftwarePlatform`, `SoftwareVersion` when applicable, `Language`, and `Respondent`.

## Quick Start

### Validate a Library Directory

```bash
python app/prism.py --validate-templates /path/to/library
```

This validates all JSON files in the directory and reports any issues.

### Example Output

```
======================================================================
Template Validation Report: /code/library/survey
======================================================================
Total files: 5 | Valid: 4 | With errors: 1 | Total errors: 2

----------------------------------------------------------------------
VALIDATION ERRORS:
----------------------------------------------------------------------

ERRORS (2):
  [ERROR] survey-mydepression.json: Study.OriginalName: Original name of the instrument is required
  [ERROR] survey-mydepression.json (ITEM01): Item description is required
    → Missing or empty 'Description' field

======================================================================
```

## Template Structure

### Minimal Valid Template

A template must have at least a `Study` section with required metadata:

```json
{
  "Study": {
    "OriginalName": "Full Instrument Name",
    "Authors": ["Author 1"],
    "Year": 2020
  }
}
```

### Complete Template with Items

```json
{
  "Study": {
    "OriginalName": "Workshop Dummy Mood Check",
    "ShortName": "Dummy Mood",
    "Authors": ["PRISM Demo Team"],
    "Year": 2026,
    "DOI": "",
    "Citation": "Dummy questionnaire for testing and demonstrations.",
    "License": "Demo content for training/testing",
    "LicenseID": "CC-BY-4.0",
    "Source": "internal-demo-template",
    "Instructions": "Read each statement and select your response."
  },
  "DM01": {
    "Description": "Current mood",
    "Levels": {
      "0": "Very positive",
      "1": "Mostly positive",
      "2": "Neutral",
      "3": "Mostly negative"
    },
    "Reversed": false
  },
  "DM02": {
    "Description": "Energy level",
    "Levels": {
      "0": "High",
      "1": "Moderate",
      "2": "Low",
      "3": "Very low"
    },
    "Reversed": false
  }
}
```

### Project-Local Administration Template

When an official survey template is copied into a project, complete the `Technical` block with the actual administration details for that dataset.

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "SoftwarePlatform": "Paper and Pencil",
    "SoftwareVersion": "",
    "Language": "de-AT",
    "Respondent": "self",
    "AdministrationMethod": "paper"
  },
  "Study": {
    "TaskName": "pss",
    "OriginalName": "Perceived Stress Scale",
    "LicenseID": "Proprietary"
  },
  "Metadata": {
    "SchemaVersion": "1.1.1",
    "CreationDate": "2026-04-01"
  }
}
```

The structure does not change between official and project templates. The difference is what the fields mean: the official library keeps the instrument definition, while the project copy records the administration instance.

### Multilingual Template

For templates available in multiple languages:

```json
{
  "I18n": {
    "Languages": ["en", "de"],
    "DefaultLanguage": "en",
    "TranslationMethod": "forward-backward"
  },
  "Study": {
    "OriginalName": {
      "en": "Dummy Emotional Check",
      "de": "Dummy Emotions-Check"
    },
    "Instructions": {
      "en": "Please rate each statement...",
      "de": "Bitte bewerten Sie jede Aussage..."
    }
  },
  "DEMO01": {
    "Description": {
      "en": "I found it easy to focus on one task at a time",
      "de": "Ich konnte mich gut auf eine Aufgabe gleichzeitig konzentrieren"
    },
    "Levels": {
      "0": {
        "en": "Never",
        "de": "Nie"
      },
      "1": {
        "en": "Sometimes",
        "de": "Manchmal"
      }
    }
  }
}
```

## Study Metadata Fields

### Required Fields

- **OriginalName** (string or object) - Full canonical name of the instrument. If object, must include "en" key.

### Optional Fields (Recommended)

- **ShortName** (string or object) - Common abbreviation (previously `Abbreviation`, which is still accepted for backward compatibility)
- **Version** (string or object) - Instrument version (e.g., "II", "5.0")
- **Authors** (array) - List of instrument authors
- **Year** (integer) - Publication/creation year (1900-2100)
- **DOI** (string) - Digital Object Identifier (format: 10.xxxx/...)
- **Citation** (string) - Full citation text
- **License** (string or object) - License terms
- **LicenseID** (string) - Normalized license (SPDX recommended)
- **Source** (string) - URL to instrument repository
- **ItemCount** (integer) - Total number of items (previously `NumberOfItems`, which is still accepted for backward compatibility)
- **Instructions** (string or object) - Administration instructions
- **Publisher** (string) - Publisher name

## Item Definition Fields

### Required Fields

- **Description** (string or object) - Item text/question. If object, must include "en" key.

### Optional Fields

- **Levels** (object) - Response options with numeric keys
  - Each level can be a string or object (for i18n)
  - Keep level text as plain labels; scoring logic belongs in recipe files
- **Reversed** (boolean) - Whether item is reverse-coded
- **Range** (object) - Min/max values: `{"min": 0, "max": 100}`
- **DataType** (string) - Data type (e.g., "numeric", "categorical")
- **Required** (boolean) - Whether item is mandatory
- **Instructions** (string) - Item-specific instructions
- **Aliases** (array) - Alternative item names
- **AliasOf** (string) - Canonical item this aliases

## Validation Rules

### JSON Structure

❌ **Error**: File is not valid JSON
✅ **Solution**: Use a JSON validator (jsonlint, your editor)

### Study Metadata

❌ **Error**: Study.OriginalName is missing
✅ **Solution**: Add the full instrument name in Study.OriginalName

❌ **Error**: Study.Year = 2050 (seems incorrect)
⚠️ **Warning**: Check that the year is correct

❌ **Error**: Study.DOI = "not a doi"
⚠️ **Warning**: DOI should start with "10." or "https://doi.org/"

### Item Definitions

❌ **Error**: Item ITEM01 is not an object
✅ **Solution**: Item definitions must be objects, not strings/arrays

❌ **Error**: Item ITEM01 missing Description
✅ **Solution**: Every item must have a Description field

### Internationalization

❌ **Error**: Study.OriginalName is object but missing 'en' key
✅ **Solution**: If using multi-language objects, 'en' is required

⚠️ **Warning**: I18n.Languages has invalid code "english"
✅ **Solution**: Use standard language codes (en, de, fr, en-US, etc.)

⚠️ **Warning**: I18n.DefaultLanguage not in Languages array
✅ **Solution**: Ensure DefaultLanguage is in the Languages list

## Python API

You can also validate templates programmatically:

```python
from template_validator import validate_templates, TemplateValidator

# Simple function (recommended)
errors, summary = validate_templates('/path/to/library')

# Detailed validation with class
validator = TemplateValidator('/path/to/library')
errors, summary = validator.validate_directory()

# Validate single file
errors = validator.validate_file('/path/to/survey.json')

# Check error details
for error in errors:
    print(f"{error.file}: {error.message}")
    if error.item:
        print(f"  Item: {error.item}")
    if error.details:
        print(f"  Details: {error.details}")
```

## Error Types

### json_parse
The file cannot be parsed as JSON. Check for:
- Trailing commas
- Missing quotes
- Unescaped characters
- Invalid syntax

### missing_study
No Study section found. Add a Study object with required metadata.

### study_validation
Study metadata is invalid:
- Missing required fields
- Invalid field formats
- Incorrect data types

### item_validation
Item definitions are invalid:
- Not an object
- Missing Description
- Invalid Levels structure
- Invalid Reversed type

### i18n_validation
Internationalization structure is invalid:
- Missing language keys
- Invalid language codes
- Inconsistent translations

## Best Practices

### 1. **Use Standard Language Codes**
```json
"Languages": ["en", "de", "fr"]  // ✅ Good
"Languages": ["English", "German"]  // ❌ Bad
```

### 2. **Consistent i18n Structure**
```json
"Description": {
  "en": "English text",
  "de": "German text"
}  // ✅ Good - all languages

"Description": {
  "en": "English text",
  "de": "German text",
  "fr": "French text"  // Use if language list includes it
}
```

### 3. **Proper DOI Format**
```json
"DOI": "10.1037/t00742-000"
"DOI": "https://doi.org/10.1037/t00742-000"
"DOI": "doi: 10.1037/t00742-000"
```

### 4. **Item Organization**
```json
{
  "Study": {},
  "ITEM01": {},
  "ITEM02": {}
}

{
  "ITEM01": {},
  "Study": {}
}
```

### 5. **Meaningful Item IDs**
```json
{
  "PHQ01": {},
  "Item_1": {},
  "a": {}
}
```

## Troubleshooting

### "No items found but Study exists - why is that OK?"

Templates can be metadata-only (skeleton templates) that just provide information about an instrument without item definitions. This is valid for:
- Pre-publication instruments
- Licensing/copyright information only
- Instruments referenced in documentation

### "My template has items but they're not being validated"

Check that items are defined as top-level keys in the JSON, not in a "Questions" section (unless you're using the Questions structure).

Both of these are valid:

```json
{
  "Study": {},
  "ITEM01": {}
}
```

```json
{
  "Study": {},
  "Questions": {
    "ITEM01": {}
  }
}
}
```

### "I want to use my own schema"

The current validator uses built-in rules. For custom validation, extend the `TemplateValidator` class:

```python
from template_validator import TemplateValidator

class MyValidator(TemplateValidator):
    REQUIRED_ITEM_FIELDS = {
        "Description": "...",
        "MyCustomField": "..."
    }
    
    def _validate_item_structure(self, file_name, item_id, item_def):
        errors = super()._validate_item_structure(file_name, item_id, item_def)
        # Add custom validation
        return errors
```

## Integration with PRISM Validation

Template validation is separate from dataset validation. Use them together:

```bash
# 1. First validate your templates
python app/prism.py --validate-templates /code/library/survey

# 2. Then validate your dataset (using those templates)
python app/prism.py /code/my-study --library /code/library
```

## See Also

- [BIDS Specification](https://bids-standard.github.io/)
- PRISM Schemas: `app/schemas/`
- [Dataset Validation](VALIDATOR.md)
