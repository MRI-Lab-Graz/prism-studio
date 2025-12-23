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
| `SoftwarePlatform` | **REQUIRED** | `string` | Platform used (e.g., `"LimeSurvey 5.0"`). |
| `Language` | **REQUIRED** | `string` | Language code (e.g., `"en"`, `"de-AT"`). |
| `Respondent` | **REQUIRED** | `string` | Who answered (e.g., `"self"`, `"parent"`). |
| `ResponseType` | RECOMMENDED | `array` | Input method (e.g., `["button"]`, `["slider"]`). |

### `Study` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `TaskName` | **REQUIRED** | `string` | Short identifier (e.g., `"bdi"`). |
| `OriginalName` | **REQUIRED** | `string` | Full name (e.g., `"Beck Depression Inventory"`). |
| `Version` | OPTIONAL | `string` | Instrument version. |
| `Citation` | OPTIONAL | `string` | Reference citation. |

### Question Item Fields

Any top-level key that is not one of the above objects is considered a question definition (e.g., `"Q01"`, `"item_1"`).

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Description` | **REQUIRED** | `string` | The exact text of the question presented. |
| `Levels` | OPTIONAL | `object` | Mapping of numeric values to text labels. |
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
    "Respondent": "self"
  },
  "Study": {
    "TaskName": "bdi",
    "OriginalName": "Beck Depression Inventory"
  },
  "Metadata": {
    "SchemaVersion": "1.0.0",
    "CreationDate": "2025-01-01"
  },
  "Q01": {
    "Description": "I feel sad",
    "Levels": {
      "0": "I do not feel sad.",
      "1": "I feel sad",
      "2": "I am sad all the time and I can't snap out of it.",
      "3": "I am so sad and unhappy that I can't stand it."
    }
  }
}
```
