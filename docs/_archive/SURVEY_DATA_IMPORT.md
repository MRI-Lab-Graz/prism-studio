# Survey Data Import Workflow

This document describes the **current** PRISM workflow for importing survey definitions from Excel and converting wide survey exports (`.xlsx` or LimeSurvey `.lsa`) into a PRISM/BIDS-style dataset.

Key points:

- Survey and biometrics templates are imported from **separate Excel files**.
- Survey templates can be **multilingual (DE/EN)** in the library.
- Dataset sidecars must be **single-language** to validate against the stable schema; use `--lang` at conversion time.

## 1) Start from the provided Excel templates

Do **not** combine survey + biometrics in one Excel.

- Survey template: [docs/examples/survey_import_template.xlsx](docs/examples/survey_import_template.xlsx)
- Biometrics template: [docs/examples/biometrics_import_template.xlsx](docs/examples/biometrics_import_template.xlsx)

Both templates include a **Help** sheet explaining all column names and options. They also include placeholder participant-facing instruction text (DE/EN) that you should replace with the **exact wording** used in your study.

## 2) Survey Excel format (minimal vs advanced)

The survey importer is header-based (column names). The template contains all supported columns.

### Minimal columns (start here)

Per item/row:

- `VariableName` (item ID; becomes the TSV column name)
- `Group` (instrument ID; becomes the survey template file name `survey-<group>.json`)
- One of:
  - `Question_de` / `Question_en` (recommended), or
  - `Question` (fallback, single-language)
- One of:
  - `Scale_de` / `Scale_en` (recommended), or
  - `Scale` (fallback)

### Advanced optional columns

Item-level validation/semantics:

- `Units`, `DataType`, `AllowedValues`
- `MinValue`, `MaxValue`, `WarnMinValue`, `WarnMaxValue`
- `TermURL`, `Relevance`
- `AliasOf`, `Session`, `Run`

Instrument-level metadata (repeat in any row; first non-empty per `Group` wins):

- `OriginalName_de`, `OriginalName_en`, `ShortName`
- `Version_de`, `Version_en`, `StudyDescription_de`, `StudyDescription_en`
- `Authors`, `DOI`, `Citation`
- `Construct_de`, `Construct_en`, `Keywords`
- `Reliability_de`, `Reliability_en`, `Validity_de`, `Validity_en`
- `Instructions_de`, `Instructions_en` (participant-facing instructions)
- `Respondent`, `AdministrationMethod`, `SoftwarePlatform`, `SoftwareVersion`
- `Languages`, `DefaultLanguage`, `TranslationMethod`

### Multilingual (i18n) JSON output

The imported survey library JSON uses the repo’s i18n convention:

- `Study.OriginalName`, `Study.Version`, `Study.Description`, `Study.Instructions` are language maps like `{ "de": "…", "en": "…" }`.
- Each item’s `Description` is `{ "de": "…", "en": "…" }`.
- Each item’s `Levels` is a dict of dicts: `{ "0": {"de": "Nie", "en": "Never"}, ... }`.

## 3) Import the survey Excel into a library

Recommended:

```bash
python prism_tools.py survey import-excel --excel metadata.xlsx --output survey_library
```

Or (equivalent low-level script):

```bash
python scripts/excel_to_library.py --excel metadata.xlsx --output survey_library
```

This produces `survey_library/survey-*.json` survey templates.

## 4) Convert wide survey exports into a dataset

Convert a wide `.xlsx` export (one row per participant, one column per item) into a PRISM dataset:

```bash
python prism_tools.py survey convert \
  --input responses.xlsx \
  --library survey_library \
  --output my_dataset \
  --lang de
```

Notes:

- `--lang` selects the language for i18n templates and writes schema-valid single-language sidecars.
- Survey IDs / task names are normalized to **alphanumeric** for BIDS-safe filenames. For example, `demo_survey` becomes `demosurvey` in filenames; the mapping report prints the normalized value.

## 5) Validate

```bash
python prism.py my_dataset
```

## Biometrics (separate Excel)

Biometrics templates are imported separately:

```bash
python prism_tools.py biometrics import-excel --excel biometrics.xlsx --output biometrics_library
```
