# Survey Templates

The reference model for survey templates — structure, fields, and validation —
rather than the step-by-step editing workflow. For interactive editing, use
[Template Editor](studio/template_editor.md).

A survey template is a JSON description of a questionnaire: what the instrument is,
how items are named/described, which response options belong to each item, and how
the questionnaire was administered in the project. The same conceptual template
appears in two roles: the **official/global template** (canonical reference,
`official/library/survey/`) and the **project-local copy** (what your project
actually uses and completes, `code/library/survey/`). For everyday project work,
the project-local copy is what matters.

## `Study` and `Technical` blocks

- **`Study`** describes the instrument itself. Required: `OriginalName` (string or
  `{en: ...}` object). Optional/recommended: `TaskName` (connects the template to
  filenames and task usage — matters especially for project-local copies),
  `ShortName` (was `Abbreviation`, still accepted), `Version`, `Authors`, `Year`
  (1900–2100), `DOI` (`10.xxxx/...`), `Citation`, `License`/`LicenseID` (SPDX
  recommended), `Source`, `ItemCount` (was `NumberOfItems`, still accepted),
  `Instructions`, `Publisher`.
- **`Technical`** describes how the survey was actually run in *this* project:
  `StimulusType`, `FileFormat`, `Language`, `Respondent`, `AdministrationMethod`,
  `SoftwarePlatform`, `SoftwareVersion`. Often the block that still needs
  project-specific completion after an import or template copy.
- **Items** are their own top-level keys (e.g. `PSS01`, `ADS03`). Required:
  `Description` (string or object with an `en` key). Optional: `Levels` (response
  options, numeric keys, each a string or i18n object — keep level text as plain
  labels, scoring logic belongs in recipe files), `Reversed` (boolean), `Range`
  (`{"min": 0, "max": 100}`), `DataType`, `Required`, `Instructions`, `Aliases`,
  `AliasOf`.

## Examples

**Minimal valid template:**

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

## Validating templates

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

Template validation is separate from dataset validation — use them together:

```bash
prism-validator --validate-templates /code/library/survey   # 1. templates
prism-validator /code/my-study --library /code/library       # 2. dataset
```

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

## Best practices and common mistakes

Use standard language codes (`["en", "de", "fr"]`, not `["English", "German"]`).
Keep i18n structure consistent — provide every listed language for each translated
field. Use a real DOI format (`10.1037/t00742-000` or the `https://doi.org/...`
form). Put `Study` first among top-level keys, then items, for readability. Use
meaningful item IDs (`PHQ01`, not `a`).

Avoid: treating the official library file as the normal project editing target;
leaving `Technical` incomplete after import; changing `TaskName` without
considering the dataset naming that depends on it; assuming item columns are
self-explanatory without descriptions or levels.

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

## What's next

- [Template Editor](studio/template_editor.md)
- [Survey Import](studio/converter_survey.md)
- [Validator](studio/validator.md) · [specs/survey](specs/survey)
