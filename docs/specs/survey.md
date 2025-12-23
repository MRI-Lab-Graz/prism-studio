# Survey

The `survey` modality is a PRISM extension for handling complex questionnaires. It treats surveys as rich data with detailed metadata, rather than simple phenotypic variables.

> [!TIP]
> **Starting a new survey?** Use the [Survey Import Template](../examples/survey_import_template.xlsx) to define your variables in Excel. It includes a **Help** sheet explaining all options.

## File Name Structure

Survey data files MUST follow this naming convention:

`sub-<label>[_ses-<label>]_survey-<label>.tsv`

*Note: The legacy format `_task-<label>_beh.tsv` is also supported but deprecated.*

## Sidecar JSON (`*_survey.json`)

The survey sidecar defines the structure, content, and administrative metadata of the questionnaire.

### Top-Level Objects

| Object | Requirement | Description |
| --- | --- | --- |
| `Technical` | **REQUIRED** | Platform and respondent details. |
| `Study` | **REQUIRED** | Instrument identification. |
| `Metadata` | **REQUIRED** | Schema and creation details. |
| `*` | OPTIONAL | Any other key is treated as a Question Item. |

### `Technical` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `StimulusType` | **REQUIRED** | `string` | MUST be `"Questionnaire"`. |
| `FileFormat` | **REQUIRED** | `string` | MUST be `"tsv"`. |
| `SoftwarePlatform` | OPTIONAL | `string` | Platform used (e.g., `"LimeSurvey"`, `"REDCap"`). |
| `Language` | **REQUIRED** | `string` | Language code (e.g., `"en"`, `"de-AT"`). |
| `Respondent` | **REQUIRED** | `string` | Who answered (e.g., `"self"`, `"parent"`). |
| `ResponseType` | RECOMMENDED | `array` | Input method (e.g., `["button"]`, `["slider"]`). |

> Note: PRISM supports bilingual (i18n) *source templates* and single-language *compiled* templates. See the i18n section below.

### `I18n` Object (Optional)

If present, `I18n` describes which languages are available in the template.

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Languages` | OPTIONAL | `array` | List of language codes available in the template. |
| `DefaultLanguage` | OPTIONAL | `string` | Default language when compiling/exporting. |
| `TranslationMethod` | OPTIONAL | `string` | Translation validation approach (e.g., `forward-backward`). |

### `Study` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `TaskName` | **REQUIRED** | `string` | Short identifier (e.g., `"bdi"`). |
| `OriginalName` | **REQUIRED** | `string` | Full name (e.g., `"Beck Depression Inventory"`). |
| `Version` | OPTIONAL | `string` | Instrument version. |
| `Citation` | OPTIONAL | `string` | Reference citation. |
| `DOI` | OPTIONAL | `string` | DOI for the instrument. |
| `Authors` | OPTIONAL | `array` | Instrument authors. |
| `License` / `LicenseID` / `LicenseURL` | OPTIONAL | `string` | Rights and license information. |
| `Access` | OPTIONAL | `string` | High-level access classification (`public`, `permission-required`, `licensed`, `unknown`). |
| `CopyrightHolder` | OPTIONAL | `string` | Rights holder (publisher, consortium, etc.). |
| `PermissionsNote` / `PermissionsURL` | OPTIONAL | `string` | Short usage constraint note and/or a URL to the statement. |
| `References` | OPTIONAL | `array` | Structured list of references (primary paper, manual, translation, norms, etc.). |
| `Translation` | OPTIONAL | `object` | Translation/adaptation provenance (source/target language, validated, reference). |

### Question Item Fields

Any top-level key that is not one of the above objects is considered a question definition (e.g., `"Q01"`, `"item_1"`).

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Description` | **REQUIRED** | `string` \| `object` | The exact text of the question (string) or an i18n map (e.g., `{ "de": "…", "en": "…" }`). |
| `Levels` | OPTIONAL | `object` | Mapping of numeric values to labels. Values may be strings or i18n maps. |
| `Units` | OPTIONAL | `string` | Units (if applicable). |
| `TermURL` | OPTIONAL | `string` | URL to an ontology term. |

## Example Sidecar

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "SoftwarePlatform": "LimeSurvey",
    "Language": "en",
    "Respondent": "self",
    "ResponseType": ["button"]
  },
  "I18n": {
    "Languages": ["en", "de"],
    "DefaultLanguage": "en"
  },
  "Study": {
    "TaskName": "bdi",
    "OriginalName": {
      "en": "Beck Depression Inventory",
      "de": "Beck-Depressions-Inventar"
    },
    "Version": "II",
    "Authors": ["Beck"],
    "DOI": "10.xxxx/xxxxx",
    "License": "Permission required for reuse",
    "Access": "permission-required",
    "References": [
      {
        "Type": "manual",
        "Citation": "Beck et al. (1996). BDI-II manual.",
        "URL": "https://example.org"
      }
    ],
    "Translation": {
      "SourceLanguage": "en",
      "TargetLanguage": "de",
      "Validated": true,
      "Reference": "(translation validation citation / DOI / URL)"
    }
  },
  "Metadata": {
    "SchemaVersion": "1.1.1",
    "CreationDate": "2025-01-01"
  },
  "Q01": {
    "Description": {
      "en": "I feel sad",
      "de": "Ich fühle mich traurig"
    },
    "Levels": {
      "0": {
        "en": "I do not feel sad.",
        "de": "Ich fühle mich nicht traurig."
      },
      "1": {
        "en": "I feel sad",
        "de": "Ich fühle mich traurig"
      }
    }
  }
}
```
