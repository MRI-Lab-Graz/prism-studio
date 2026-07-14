# Template Validation

The PRISM template validator checks that survey and biometrics JSON templates are
properly structured — essential when preparing custom project templates or
maintaining template libraries. It checks: valid JSON structure, required `Study`
metadata, item structure, internationalization (language codes/consistency), and
field formats (years, DOIs, language codes).

Keep two cases separate: **official library templates** (`official/library/survey/`)
describe the canonical instrument; **project templates** (`code/library/survey/`)
describe the actual administration in that project and are expected to complete
`Technical` fields — especially `AdministrationMethod`, `SoftwarePlatform`,
`SoftwareVersion` (when applicable), `Language`, and `Respondent`.

## Quick start

```bash
prism-validator --validate-templates /path/to/library
```

```text
======================================================================
Template Validation Report: /code/library/survey
======================================================================
Total files: 5 | Valid: 4 | With errors: 1 | Total errors: 2

ERRORS (2):
  [ERROR] survey-mydepression.json: Study.OriginalName: Original name of the instrument is required
  [ERROR] survey-mydepression.json (ITEM01): Item description is required
    → Missing or empty 'Description' field
```

## Template structure

**Minimal valid template** — a `Study` section with required metadata:

```json
{ "Study": { "OriginalName": "Full Instrument Name", "Authors": ["Author 1"], "Year": 2020 } }
```

**With items:**

```json
{
  "Study": {
    "OriginalName": "Workshop Dummy Mood Check",
    "ShortName": "Dummy Mood",
    "Authors": ["PRISM Demo Team"],
    "Year": 2026,
    "LicenseID": "CC-BY-4.0",
    "Instructions": "Read each statement and select your response."
  },
  "DM01": {
    "Description": "Current mood",
    "Levels": { "0": "Very positive", "1": "Mostly positive", "2": "Neutral", "3": "Mostly negative" },
    "Reversed": false
  }
}
```

**Project-local administration** — when an official template is copied into a
project, complete `Technical` with the actual administration details for that
dataset. The structure doesn't change between official and project templates; only
what the fields mean does — official keeps the instrument definition, the project
copy records the administration instance.

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "SoftwarePlatform": "Paper and Pencil",
    "Language": "de-AT",
    "Respondent": "self",
    "AdministrationMethod": "paper"
  },
  "Study": { "TaskName": "pss", "OriginalName": "Perceived Stress Scale", "LicenseID": "Proprietary" }
}
```

**Multilingual template:**

```json
{
  "I18n": { "Languages": ["en", "de"], "DefaultLanguage": "en", "TranslationMethod": "forward-backward" },
  "Study": {
    "OriginalName": { "en": "Dummy Emotional Check", "de": "Dummy Emotions-Check" }
  },
  "DEMO01": {
    "Description": { "en": "I found it easy to focus on one task at a time", "de": "Ich konnte mich gut auf eine Aufgabe gleichzeitig konzentrieren" },
    "Levels": { "0": { "en": "Never", "de": "Nie" }, "1": { "en": "Sometimes", "de": "Manchmal" } }
  }
}
```

## Field reference

**`Study` fields** — required: `OriginalName` (string or `{en: ...}` object).
Optional/recommended: `ShortName` (was `Abbreviation`, still accepted),
`Version`, `Authors`, `Year` (1900–2100), `DOI` (`10.xxxx/...`), `Citation`,
`License`/`LicenseID` (SPDX recommended), `Source`, `ItemCount` (was
`NumberOfItems`, still accepted), `Instructions`, `Publisher`.

**Item fields** — required: `Description` (string or object with `en` key).
Optional: `Levels` (response options, numeric keys, each a string or i18n object —
keep level text as plain labels, scoring logic belongs in recipe files), `Reversed`
(boolean), `Range` (`{"min": 0, "max": 100}`), `DataType`, `Required`,
`Instructions`, `Aliases`, `AliasOf`.

## Validation rules and error types

| Check | Error | Fix |
|---|---|---|
| JSON structure | File is not valid JSON | Use a JSON validator (jsonlint, your editor) |
| Study metadata | `Study.OriginalName` missing | Add the full instrument name |
| Study metadata | `Study.Year` looks wrong (e.g. 2050) | Check the year is correct |
| Study metadata | `Study.DOI` malformed | Should start with `10.` or `https://doi.org/` |
| Item definitions | Item is not an object | Item definitions must be objects, not strings/arrays |
| Item definitions | Item missing `Description` | Every item must have a `Description` field |
| Internationalization | Object missing `en` key | `en` is required in multi-language objects |
| Internationalization | Invalid language code (e.g. "english") | Use standard codes: `en`, `de`, `fr`, `en-US` |
| Internationalization | `DefaultLanguage` not in `Languages` | Ensure it's listed |

Error types returned by the API: **`json_parse`** (unparseable — trailing commas,
missing quotes, unescaped characters); **`missing_study`** (no `Study` section);
**`study_validation`** (missing required fields, invalid formats/types);
**`item_validation`** (not an object, missing `Description`, invalid `Levels`/
`Reversed`); **`i18n_validation`** (missing language keys, invalid codes,
inconsistent translations).

## Python API

```python
from template_validator import validate_templates, TemplateValidator

errors, summary = validate_templates('/path/to/library')       # simple function

validator = TemplateValidator('/path/to/library')               # detailed
errors, summary = validator.validate_directory()
errors = validator.validate_file('/path/to/survey.json')        # single file

for error in errors:
    print(f"{error.file}: {error.message}")
```

For custom validation, extend `TemplateValidator`:

```python
class MyValidator(TemplateValidator):
    REQUIRED_ITEM_FIELDS = {"Description": "...", "MyCustomField": "..."}

    def _validate_item_structure(self, file_name, item_id, item_def):
        return super()._validate_item_structure(file_name, item_id, item_def)
```

## Best practices

Use standard language codes (`["en", "de", "fr"]`, not `["English", "German"]`).
Keep i18n structure consistent — provide every listed language for each translated
field. Use a real DOI format (`10.1037/t00742-000` or the `https://doi.org/...`
form). Put `Study` first among top-level keys, then items, for readability. Use
meaningful item IDs (`PHQ01`, not `a`).

## Troubleshooting

**"No items found but Study exists — is that OK?"** Yes — templates can be
metadata-only (skeleton templates) describing an instrument without item
definitions: pre-publication instruments, licensing/copyright-only entries, or
instruments only referenced in documentation.

**"My template has items but they're not being validated"** Check items are
top-level keys, not nested under a `"Questions"` key (unless you're deliberately
using the `Questions` structure — both forms are valid).

**"I want to use my own schema"** The validator uses built-in rules; extend
`TemplateValidator` as shown above for custom validation.

## See also

Template validation is separate from dataset validation — use them together:

```bash
prism-validator --validate-templates /code/library/survey   # 1. templates
prism-validator /code/my-study --library /code/library       # 2. dataset
```

- [BIDS Specification](https://bids-standard.github.io/)
- PRISM Schemas: `app/schemas/`
- [Validator](studio/validator.md)
