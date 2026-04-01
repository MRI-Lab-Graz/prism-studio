# Survey

The `survey` modality is a PRISM extension for handling complex questionnaires. It treats surveys as rich data with detailed metadata, rather than simple phenotypic variables.

> [!TIP]
> **Starting a new survey?** Use the [Survey Import Template](../examples/survey_import_template.xlsx) to define your variables in Excel. It includes a **Help** sheet explaining all options.

## Import Template Layout

The Excel import template is split into dedicated sheets:

- `Items`: item-level columns (`ItemID`, `Description`, `Scale`, `Session`, `Run`, etc.)
- `General`: transposed survey-level metadata with `Field` + `Value` rows (`OriginalName_*`, `Version_*`, `Instructions_*`, citation, i18n settings, etc.)
- `Help`: quick reference for column semantics and examples

The importer merges these sheets automatically.

In `General`, rows marked red in the `Required` column indicate schema-critical metadata entries.

## Multilingual Columns

For multilingual templates, use language suffix columns:

- `Description_<lang>` and `Scale_<lang>` for item text and levels
- `OriginalName_<lang>`, `Version_<lang>`, `Instructions_<lang>`, `Construct_<lang>`, `StudyDescription_<lang>` for survey metadata

Examples:

- `Description_de`, `Description_en`, `Description_fr`
- `OriginalName_de`, `OriginalName_en`, `OriginalName_fr`

`_de` / `_en` remains fully supported, and additional language tags are preserved in the generated i18n template.

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
| `Scoring` | OPTIONAL | Scoring and interpretation rules. |
| `Normative` | OPTIONAL | Normative data and reference values. |
| `Metadata` | **REQUIRED** | Schema and creation details. |
| `*` | OPTIONAL | Any other key is treated as a Question Item. |

### Official Library vs Project Copy

PRISM uses the same JSON shape in two contexts:

- **Official library template**: the canonical instrument definition in `official/library/survey/`
- **Project copy**: the project-local administration template in `code/library/survey/`

The split is intentional:

- The **official library** should describe the instrument itself: canonical name, references, item texts, levels, scale metadata, and other properties that remain true across projects.
- The **project copy** should describe how that instrument was actually administered in a specific dataset: language used, respondent, online vs paper, software platform, software version, and any project-specific adaptations.

This means administration metadata stays in the existing `Technical` block. Do **not** add a separate top-level `Administration` object.

In practice:

- `Technical.AdministrationMethod` = how the instrument was administered in the project (`online`, `paper`, `interview`, `phone`, `mixed`)
- `Technical.SoftwarePlatform` = with what it was administered in the project (`LimeSurvey`, `PsychoPy`, `Pavlovia`, `Paper and Pencil`, `Other`)
- `Technical.SoftwareVersion` = software version when applicable

When templates are copied from the official library into a project, these project-local `Technical` fields should be completed there.

### `Technical` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `StimulusType` | **REQUIRED** | `string` | MUST be `"Questionnaire"`. |
| `FileFormat` | **REQUIRED** | `string` | MUST be `"tsv"`. |
| `SoftwarePlatform` | OPTIONAL | `string` | Project-local platform used for administration (e.g., `"LimeSurvey"`, `"Paper and Pencil"`). |
| `SoftwareVersion` | OPTIONAL | `string` | Project-local version of the software platform. |
| `Language` | **REQUIRED** | `string` | Project-local language code actually administered (e.g., `"en"`, `"de-AT"`). |
| `Respondent` | **REQUIRED** | `string` | Project-local respondent type (e.g., `"self"`, `"parent"`). |
| `AdministrationMethod` | OPTIONAL | `string` | Project-local administration mode (`online`, `paper`, `interview`, `phone`, `mixed`). |
| `ResponseType` | RECOMMENDED | `array` | Input method (e.g., `["button"]`, `["slider"]`). |
| `Equipment` | OPTIONAL | `string` | Hardware used (e.g., `Stopwatch`, `Dynamometer`). |
| `Supervisor` | OPTIONAL | `string` | Who supervised the test (`investigator`, `physician`, `self`). |
| `Location` | OPTIONAL | `string` | Where it took place (`laboratory`, `clinic`, `home`). |

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
| `TaskName` | **REQUIRED** | `string` | Project-local task identifier (e.g., `"moodcheck"`). |
| `OriginalName` | **REQUIRED** | `string` | Full name (e.g., `"Dummy Mood Check"`). |
| `ShortName` | OPTIONAL | `string` \| `object` | Common abbreviation (e.g., `DMC-5`). |
| `Version` | OPTIONAL | `string` | Instrument version. |
| `Citation` | OPTIONAL | `string` | Reference citation. |
| `DOI` | OPTIONAL | `string` | DOI for the instrument. |
| `Authors` | OPTIONAL | `array` | Instrument authors. |
| `License` / `LicenseID` / `LicenseURL` | OPTIONAL | `string` | Rights and license information. |
| `Access` | OPTIONAL | `string` | High-level access classification (`public`, `permission-required`, `licensed`, `unknown`). |
| `CopyrightHolder` | OPTIONAL | `string` | Rights holder (publisher, consortium, etc.). |
| `PermissionsNote` / `PermissionsURL` | OPTIONAL | `string` | Short usage constraint note and/or a URL to the statement. |
| `Construct` | OPTIONAL | `string` \| `object` | Psychological construct measured (e.g., `depression`). |
| `Keywords` | OPTIONAL | `array` | Keywords describing the instrument. |
| `Description` | OPTIONAL | `string` \| `object` | Detailed description or abstract. |
| `Instructions` | OPTIONAL | `string` \| `object` | Instructions given to the participant. |
| `Reliability` / `Validity` | OPTIONAL | `string` \| `object` | Psychometric properties. |
| `AdministrationTime` | OPTIONAL | `string` \| `object` | Estimated time to complete. |
| `References` | OPTIONAL | `array` | Structured list of references (objects with `Type`, `Citation`, canonical `DOI`, `URL`, optional `Year`, and `Notes`). |
| `Translation` | OPTIONAL | `object` | Translation/adaptation provenance (source/target language, validated, reference). |

### `Scoring` Object Fields (Optional)

Defines how the data should be interpreted or scored.

| Key | Type | Description |
| --- | --- | --- |
| `ScoringMethod` | `string` | General method (e.g., `sum`, `mean`). |
| `ScoreRange` | `object` | Possible `min` and `max` scores. |
| `Cutoffs` | `object` | Clinical thresholds and their interpretations. |
| `ReverseCodedItems` | `array` | List of items that need inversion. |
| `Subscales` | `array` | Structured definitions of sub-scores (Name, Items, Method). |

### `Normative` Object Fields (Optional)

| Key | Type | Description |
| --- | --- | --- |
| `ReferencePopulation` | `string` | Population on which normative data is based. |
| `ReferenceSource` | `string` | Citation for normative data. |
| `Percentiles` | `object` | Percentile cutoffs (e.g., `{"p50": 15}`). |

### Question Item Fields

Any top-level key that is not one of the above objects is considered a question definition (e.g., `"Q01"`, `"item_1"`).

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Description` | **REQUIRED** | `string` \| `object` | The exact text of the question (string) or an i18n map (e.g., `{ "de": "…", "en": "…" }`). |
| `Levels` | OPTIONAL | `object` | Mapping of numeric values to labels. Values may be strings or i18n maps. |
| `Unit` / `Units` | OPTIONAL | `string` | Units (if applicable). |
| `TermURL` | OPTIONAL | `string` | URL to an ontology term. |
| `Relevance` | OPTIONAL | `string` | Logic for when this item is applicable (e.g., `Q01 == 1`). |
| `MinValue` / `MaxValue` | OPTIONAL | `number` | Hard bounds for validation. |
| `WarnMinValue` / `WarnMaxValue` | OPTIONAL | `number` | Soft bounds (triggers warnings). |
| `AllowedValues` | OPTIONAL | `array` | List of allowed values. |
| `DataType` | OPTIONAL | `string` | Expected type (`string`, `integer`, `float`). |
| `SessionHint` / `RunHint` | OPTIONAL | `string` | Used for longitudinal/repeated data mapping. |

### `Study.References` Objects

Each entry in `Study.References` must specify a `Type` from the available enum, and it may include a `Citation`, canonical `DOI` (`10.x/...`), and a `URL` (`uri` format). Additional optional metadata includes `Year` (integer) and `Notes`, which can be a string or a localized object to document translations or comments.

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
    "TaskName": "moodcheck",
    "OriginalName": {
      "en": "Dummy Mood Check",
      "de": "Dummy Stimmungs-Check"
    },
    "Version": "1.0",
    "Authors": ["PRISM Demo Team"],
    "DOI": "",
    "License": "Demo content for training/testing",
    "Access": "public",
    "References": [
      {
        "Type": "manual",
        "Citation": "Dummy questionnaire manual for PRISM testing.",
        "DOI": "",
        "URL": "https://example.org/dummy-manual",
        "Year": 2026,
        "Notes": {
          "en": "Demo manual"
        }
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
      "en": "I felt focused during my daily tasks",
      "de": "Ich war bei meinen taeglichen Aufgaben konzentriert"
    },
    "Levels": {
      "0": {
        "en": "Not at all",
        "de": "Gar nicht"
      },
      "1": {
        "en": "Somewhat",
        "de": "Teilweise"
      }
    }
  }
}
```
