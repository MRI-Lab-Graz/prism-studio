# Template Validation

The PRISM template validator helps you ensure that survey and biometrics JSON templates are properly structured and valid. This is essential when preparing custom project templates or maintaining template libraries.

## What is Template Validation?

Template validation checks survey and biometrics JSON files for:

1. **Valid JSON Structure** - File must be parseable JSON
2. **Required Metadata** - Study section with essential information
3. **Item Structure** - Individual item definitions with proper fields
4. **Internationalization (i18n)** - Language codes and consistency
5. **Field Formats** - Years, DOIs, language codes follow proper formats

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
    "OriginalName": "Beck Depression Inventory-II",
    "ShortName": "BDI-II",
    "Abbreviation": "BDI",
    "Authors": ["Aaron T. Beck"],
    "Year": 1996,
    "DOI": "10.1037/t00742-000",
    "Citation": "Beck, A.T., Steer, R.A., & Brown, G.K. (1996).",
    "License": "Commercial license required",
    "LicenseID": "proprietary",
    "Source": "https://www.pearsonclinical.com/",
    "Instructions": "Read each statement and select your response."
  },
  "BDI01": {
    "Description": "Sadness",
    "Levels": {
      "0": "I do not feel sad",
      "1": "I feel sad much of the time",
      "2": "I am sad all the time",
      "3": "I am so sad or unhappy that I can't stand it"
    },
    "Reversed": false
  },
  "BDI02": {
    "Description": "Pessimism",
    "Levels": {
      "0": "I am not discouraged about my future",
      "1": "I feel more discouraged about my future",
      "2": "I do not expect things to work out for me",
      "3": "I expect the worst and my future is hopeless"
    },
    "Reversed": false
  }
}
```

### Multilingual Template

For templates available in multiple languages:

```json
{
  "I18n": {
    "Languages": ["en", "de", "fr"],
    "DefaultLanguage": "en",
    "TranslationMethod": "forward-backward"
  },
  "Study": {
    "OriginalName": {
      "en": "Depression Anxiety Stress Scales",
      "de": "Depression Anxiety Stress Skalen",
      "fr": "Échelles de dépression, anxiété et stress"
    },
    "Instructions": {
      "en": "Please rate each statement...",
      "de": "Bitte bewerten Sie jede Aussage...",
      "fr": "Veuillez évaluer chaque affirmation..."
    }
  },
  "DASS01": {
    "Description": {
      "en": "I found myself getting upset by quite trivial things",
      "de": "Ich merkte, dass ich mich über triviale Dinge aufregte",
      "fr": "Je me suis surpris à être contrarié par des choses plutôt banales"
    },
    "Levels": {
      "0": {
        "en": "Never",
        "de": "Nie",
        "fr": "Jamais"
      },
      "1": {
        "en": "Sometimes",
        "de": "Manchmal",
        "fr": "Parfois"
      }
    }
  }
}
```

## Study Metadata Fields

### Required Fields

- **OriginalName** (string or object) - Full canonical name of the instrument. If object, must include "en" key.

### Optional Fields (Recommended)

- **ShortName** (string or object) - Common abbreviation
- **Abbreviation** (string) - Short code
- **Version** (string or object) - Instrument version (e.g., "II", "5.0")
- **Authors** (array) - List of instrument authors
- **Year** (integer) - Publication/creation year (1900-2100)
- **DOI** (string) - Digital Object Identifier (format: 10.xxxx/...)
- **Citation** (string) - Full citation text
- **License** (string or object) - License terms
- **LicenseID** (string) - Normalized license (SPDX recommended)
- **Source** (string) - URL to instrument repository
- **Instructions** (string or object) - Administration instructions
- **NumberOfItems** (integer) - Total number of items
- **Publisher** (string) - Publisher name

## Item Definition Fields

### Required Fields

- **Description** (string or object) - Item text/question. If object, must include "en" key.

### Optional Fields

- **Levels** (object) - Response options with numeric keys
  - Each level can be a string or object (for i18n)
  - Level definitions can include `{score=X}` notation
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
