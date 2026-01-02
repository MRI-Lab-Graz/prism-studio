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

You can generate biometrics JSON templates from a single-sheet Excel **codebook** (no data required) using `prism_tools.py biometrics import-excel`. See `docs/PRISM_TOOLS.rst` for the full column list and an example.

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
