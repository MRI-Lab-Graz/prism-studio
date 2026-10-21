# Biometrics

The `biometrics` modality is a PRISM extension designed for physiological assessments that do not fit into standard BIDS `beh` or `physio` categories. Examples include VO2max tests, plank tests, balance assessments, or anthropometric measurements.

> [!TIP]
> **Starting a new biometric assessment?** Use the [Biometrics Import Template](../examples/biometrics_import_template.xlsx) to define your variables in Excel. It includes a **Help** sheet explaining all options.

## File Name Structure

Biometric data files MUST follow this naming convention:

`sub-<label>[_ses-<label>]_task-<label>_biometrics.<extension>`

| Entity | Description |
| --- | --- |
| `sub` | **Required**. The subject identifier. |
| `ses` | **Optional**. The session identifier. |
| `task` | **Required**. The name of the biometric task (e.g., `task-ukk`, `task-plank`). |
| `biometrics` | **Required**. The suffix indicating the modality. |
| `extension` | **Required**. Typically `.tsv`. |

**Example:**
`sub-001_ses-01_task-ukk_biometrics.tsv`

## Sidecar JSON (`*_biometrics.json`)

Each biometric data file MUST be associated with metadata in a JSON sidecar. This file contains metadata about the assessment protocol.

PRISM follows the BIDS inheritance principle for biometrics sidecars:

- **Preferred (inherited):** one dataset-level sidecar per task, named `task-<task>_biometrics.json` in the dataset root.
- **Override (if metadata truly differs):** a subject/session-specific sidecar next to the TSV (e.g., `sub-01_ses-01_task-<task>_biometrics.json`).

### Top-Level Objects

The JSON structure is divided into three main objects to organize metadata logically.

| Object | Requirement | Description |
| --- | --- | --- |
| `Technical` | **REQUIRED** | Technical details about the data acquisition. |
| `Study` | **REQUIRED** | Scientific context, protocol details, and references. |
| `Metadata` | **REQUIRED** | Administrative metadata about the file itself. |

### `Technical` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Type` | **REQUIRED** | `string` | Type of assessment (`Biometrics`, `PhysicalPerformance`, `Anthropometry`, `FitnessTest`). |
| `FileFormat` | **REQUIRED** | `string` | The format of the data file (e.g., `"tsv"`). |
| `SoftwarePlatform` | OPTIONAL | `string` | Software used (e.g., `"My Jump Lab"`, `"Kubios"`). |
| `SoftwareVersion` | OPTIONAL | `string` | Version of the software platform. |
| `Language` | OPTIONAL | `string` | Primary language (e.g., `"en"`, `"de-AT"`). |
| `Respondent` | OPTIONAL | `string` | Who performed the test (`self`, `clinician`, etc.). |
| `Equipment` | **REQUIRED** | `string` | The device or equipment used (e.g., "Stopwatch", "Cycle Ergometer"). |
| `EquipmentManufacturer` | OPTIONAL | `string` | Manufacturer of the equipment. |
| `EquipmentModel` | OPTIONAL | `string` | Model name/number. |
| `CalibrationDate` | OPTIONAL | `string` | Date of last calibration (`YYYY-MM-DD`). |
| `Supervisor` | OPTIONAL | `string` | Who supervised the test. Allowed: `"investigator"`, `"physician"`, `"trainer"`, `"self"`. |
| `Location` | OPTIONAL | `string` | Where it took place (`laboratory`, `clinic`, `gym`, `field`, `home`). |

### `Study` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `BiometricName` | **REQUIRED** | `string` | Short alphanumeric identifier (e.g., `"ukk"`). |
| `OriginalName` | **REQUIRED** | `string` | Full human-readable name (e.g., `"UKK Walk Test"`). |
| `ShortName` | OPTIONAL | `string` \| `object` | Common abbreviation. |
| `Version` | OPTIONAL | `string` | Instrument version. |
| `Authors` | OPTIONAL | `array` | Instrument authors. |
| `Citation` | OPTIONAL | `string` | Reference citation. |
| `DOI` | OPTIONAL | `string` | DOI for the instrument. |
| `License` / `LicenseID` / `LicenseURL` | OPTIONAL | `string` | Rights and license information. |
| `Access` | OPTIONAL | `string` | High-level access classification. |
| `CopyrightHolder` | OPTIONAL | `string` | Rights holder. |
| `Construct` | OPTIONAL | `string` \| `object` | Psychological/physical construct measured. |
| `Keywords` | OPTIONAL | `array` | Keywords describing the instrument. |
| `Description` | **REQUIRED** | `string` | Detailed description of the procedure. |
| `Instructions` | RECOMMENDED | `string` | Instructions given to the participant. |
| `Reliability` / `Validity` | OPTIONAL | `string` \| `object` | Psychometric properties. |
| `AdministrationTime` | OPTIONAL | `string` \| `object` | Estimated time to complete. |
| `References` | OPTIONAL | `array` | Structured list of references. |
| `Translation` | OPTIONAL | `object` | Translation/adaptation provenance. |

### `Metadata` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `SchemaVersion` | **REQUIRED** | `string` | Version of the schema used (e.g., `"1.1.1"`). |
| `CreationDate` | **REQUIRED** | `string` | Date of file creation in `YYYY-MM-DD` format. |
| `Creator` | OPTIONAL | `string` | Tool or person who created the file. |

## Metric (Column) Definitions

In addition to the three top-level objects, a biometrics sidecar typically contains **one object per TSV column** (the column name is the JSON key). These entries document how to interpret and validate each metric.

Common fields for each metric:

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Description` | **REQUIRED** | `string` | Human-readable description of the metric/column. |
| `Units` | **REQUIRED** | `string` | Unit of measurement (e.g., `cm`, `sec`, `percent`, `score`). |
| `DataType` | OPTIONAL | `string` | Expected type: `string`, `integer`, `float`. |
| `MinValue` / `MaxValue` | OPTIONAL | `number` | Hard bounds for valid values. |
| `AllowedValues` | OPTIONAL | `array` | Enumerated allowed values (numbers/strings). |
| `Levels` | OPTIONAL | `object` | Mapping of coded values to labels (e.g., Likert scale). |
| `SessionHint` | OPTIONAL | `string` | Optional session hint for repeated assessments (e.g., `ses-1`). |
| `RunHint` | OPTIONAL | `string` | Optional run hint for repeated assessments (e.g., `run-2`). |

**Example metric with labeled levels:**

```json
"rpe_scale": {
  "Description": "Rate of perceived exertion",
  "Units": "score",
  "DataType": "integer",
  "AllowedValues": [0, 1, 2, 3],
  "Levels": {
    "0": "selten oder überhaupt nicht",
    "1": "manchmal",
    "2": "öfter",
    "3": "meistens"
  }
}
```

## Generating Templates from Excel

You can generate biometrics JSON templates from a single-sheet Excel **codebook** (no data required) using `prism_tools.py biometrics import-excel`. See [CLI Reference](../CLI_REFERENCE.md#biometrics) for the full column list and an example.

## Example Sidecar

```json
{
  "Technical": {
    "StimulusType": "Biometrics",
    "FileFormat": "tsv",
    "Equipment": "Stopwatch, Heart Rate Monitor"
  },
  "Study": {
    "BiometricName": "ukk",
    "OriginalName": "UKK 2km Walk Test",
    "Description": "Participants walk 2km as fast as possible. HR and time are recorded.",
    "Instructions": "Walk 2km at a steady, fast pace. Do not run.",
    "Reference": "Oja et al. (1991)",
    "EstimatedDuration": "15-20 min"
  },
  "Metadata": {
    "SchemaVersion": "1.1.1",
    "CreationDate": "2025-11-27"
  }
}
```

<!-- BEGIN SCHEMA REFERENCE (generated by scripts/generate_schema_reference.py; do not edit) -->

## Field reference (`biometrics.schema.json`, version 1.1.1)

Generated from [`app/schemas/stable/biometrics.schema.json`](../../app/schemas/stable/biometrics.schema.json). Nested fields are shown as `Block.Field`; `[]` marks list items. *Required* applies within its parent block.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `Technical` | object | yes | Technical biometric properties |
| `Technical.Type` | string | yes | Type of biometric assessment Allowed: `Biometrics`, `PhysicalPerformance`, `Anthropometry`, `FitnessTest`, ``. |
| `Technical.FileFormat` | string | yes | Data file format Allowed: `tsv`, ``. |
| `Technical.SoftwarePlatform` | string | no | Software platform used for data collection (e.g., My Jump Lab, Kubios) |
| `Technical.SoftwareVersion` | string | no | Version of the software platform |
| `Technical.Language` | string | no | Primary language of the assessment (e.g., en, en-US, de-AT) |
| `Technical.Respondent` | string | no | Who provided the responses/performed the test Allowed: `self`, `clinician`, `parent`, `teacher`, `caregiver`, `other`, ``. |
| `Technical.Equipment` | string / object | yes | Equipment used for measurement (e.g., Stopwatch, Cycle Ergometer, Dynamometer) |
| `Technical.EquipmentManufacturer` | string | no | Manufacturer of the equipment |
| `Technical.EquipmentModel` | string | no | Model name/number of the equipment |
| `Technical.CalibrationDate` | string | no | Date of last equipment calibration |
| `Technical.Supervisor` | string | no | Who supervised the assessment Allowed: `investigator`, `physician`, `trainer`, `physiotherapist`, `self`, ``. |
| `Technical.Location` | string | no | Where the assessment was conducted Allowed: `laboratory`, `clinic`, `gym`, `field`, `home`, ``. |
| `I18n` | object | no | Internationalization settings for multi-language biometrics |
| `I18n.Languages` | array | no | List of available languages (e.g., ['en', 'de', 'fr']) |
| `I18n.DefaultLanguage` | string | no | Default/primary language of the instrument |
| `I18n.TranslationMethod` | string | no | Method used for translation validation Allowed: `forward-backward`, `committee`, `parallel`, `original`, `validated-translation`, ``. |
| `Study` | object | yes | Study-specific assessment parameters |
| `Study.BiometricName` | string | yes | Short biometric identifier matching filename (e.g., vo2max, planks, grip) |
| `Study.OriginalName` | string / object | yes | Full name of the test (e.g., UKK Walk Test, Plank Test, Handgrip Strength) |
| `Study.ShortName` | string / object | no | Common abbreviation (e.g., VO2max, 6MWT) |
| `Study.Authors` | array | no | Authors of the test protocol |
| `Study.Citation` | string | no | DOI or citation for the test protocol |
| `Study.DOI` | string | no | Digital Object Identifier (DOI) for the test protocol |
| `Study.Category` | string | no | Category of fitness/biometric test Allowed: `cardiorespiratory`, `muscular-strength`, `muscular-endurance`, `flexibility`, `balance`, `body-composition`, `anthropometry`, ``. |
| `Study.Protocol` | string | no | Reference to the protocol used |
| `Study.Keywords` | array | no | Keywords describing the test |
| `Study.Description` | string / object | yes | Detailed description of the test procedure |
| `Study.Reliability` | string / object | no | Information about the reliability of the test |
| `Study.Validity` | string / object | no | Information about the validity of the test |
| `Study.Instructions` | string / object | no | Instructions given to the participant |
| `Study.Instruction` | string / object | no | Instructions given to the participant (alias for Instructions) |
| `Study.Reference` | string | no | Citation or reference for the test protocol |
| `Study.AdministrationTime` | object | no | Estimated time to complete the assessment in minutes |
| `Study.AdministrationTime.min` | number | yes | Minimum estimated minutes |
| `Study.AdministrationTime.max` | number | yes | Maximum estimated minutes |
| `Study.AgeRange` | object | no | Target age range for the assessment in years |
| `Study.AgeRange.min` | number | yes | Minimum age in years |
| `Study.AgeRange.max` | number | yes | Maximum age in years |
| `Study.TargetPopulation` | string / object | no | Descriptive target population (e.g., 'Clinical', 'Athletes') |
| `Study.ExclusionCriteria` | string / object | no | Conditions under which the test should not be performed |
| `Study.WarmupProtocol` | string / object | no | Warmup procedure before the test (if required) |
| `Scoring` | object | no | Scoring and interpretation information |
| `Scoring.ScoringMethod` | string / object | no | How items are scored (e.g., sum, mean, weighted, best-of-trial) |
| `Scoring.ScoreRange` | object | no | Possible score range |
| `Scoring.ScoreRange.min` | number / null | no |  |
| `Scoring.ScoreRange.max` | number / null | no |  |
| `Scoring.Cutoffs` | object | no | Clinical or performance cutoff scores and their interpretations |
| `Scoring.ReverseCodedItems` | array | no | List of reverse-coded item column names |
| `Scoring.ReverseCodingScale` | object | no | Scale bounds used for reverse coding (min/max), if applicable |
| `Scoring.ReverseCodingScale.min` | number / null | no |  |
| `Scoring.ReverseCodingScale.max` | number / null | no |  |
| `Scoring.CutoffsSource` | string / object | no | Reference for cutoffs (citation/DOI/URL) |
| `Scoring.NormsSource` | string / object | no | Reference for norms (citation/DOI/URL) |
| `Scoring.Subscales` | array | no | Optional structured subscale definitions for transparent scoring |
| `Scoring.Subscales[].Name` | string / object | no | Subscale name |
| `Scoring.Subscales[].Items` | array | no | Item IDs contributing to the subscale |
| `Scoring.Subscales[].Method` | string | no | Aggregation method Allowed: `sum`, `mean`, `weighted`, `custom`, `best`, ``. |
| `Scoring.Subscales[].Range` | object | no |  |
| `Scoring.Subscales[].Range.min` | number / null | no |  |
| `Scoring.Subscales[].Range.max` | number / null | no |  |
| `Scoring.Subscales[].ReverseCodedItems` | array | no | Reverse-coded items within this subscale |
| `Scoring.Subscales[].Note` | string / object | no | Notes about scoring or interpretation |
| `Normative` | object | no | Normative data and reference values |
| `Normative.ReferencePopulation` | string / object | no | Population on which normative data is based |
| `Normative.ReferenceSource` | string | no | Citation for normative data |
| `Normative.Percentiles` | object | no | Percentile cutoffs (e.g., {'p25': 10, 'p50': 15, 'p75': 20}) |
| `Metadata` | object | yes | Administrative metadata |
| `Metadata.SchemaVersion` | string | yes |  |
| `Metadata.CreationDate` | string | yes | Date of creation |
| `Metadata.Creator` | string | no |  |

<!-- END SCHEMA REFERENCE -->
