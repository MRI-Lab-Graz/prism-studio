# Specifications and Schemas (PRISM vs BIDS)

This page explains PRISM’s **specification layer**: how schemas work, where they live, and how they relate to standard BIDS.

PRISM is an add-on to BIDS:
- PRISM **does not replace** BIDS.
- BIDS standards should not be changed in PRISM.
- PRISM adds additional schemas (e.g., Survey, Biometrics) that are not fully standardized in BIDS yet.
- A key design goal is that standard BIDS tools/apps still work on PRISM datasets.

---

## 1) Conceptual model

### BIDS (core)
BIDS defines:
- dataset structure conventions
- filename conventions and entities (`sub-`, `ses-`, `task-`, etc.)
- standard metadata files (e.g., `dataset_description.json`, `participants.tsv`)

### PRISM (extensions)
PRISM adds:
- additional modality-specific schemas (e.g., `survey`, `biometrics`)
- **Mandatory Extensions to BIDS Core**: For certain standard BIDS modalities (like `events`), PRISM mandates additional metadata blocks (e.g., `StimulusPresentation`) that are optional or unspecified in standard BIDS.
- stricter sidecar requirements for certain data types
- optional internationalization (i18n) support for variable-level descriptions

---

## 2) Schema versions

PRISM schemas are versioned under the repository folder:
- `schemas/stable/` (default)
- `schemas/vX.Y/` (historical / pinned versions)

You can:

```bash
python prism.py --list-versions
python prism.py /path/to/dataset --schema-version stable
```

For details, see:
- [SCHEMA_VERSIONING.md](SCHEMA_VERSIONING.md)
- [SCHEMA_VERSIONING_GUIDE.md](SCHEMA_VERSIONING_GUIDE.md)

---

## 3) Files PRISM expects in a dataset

At minimum (BIDS core):
- `dataset_description.json` (required)
- `participants.tsv` (commonly required in practice)

For PRISM extensions, typical additions are:
- per-subject survey TSVs under `sub-*/ses-*/survey/`
- per-subject biometrics TSVs under `sub-*/ses-*/biometrics/`
- JSON sidecars for each data file (PRISM requires sidecars for non-JSON data files it validates)

---

## 4) Filename conventions (high-level)

PRISM follows BIDS-like entity conventions. Examples:

Survey TSV:
- `sub-001_ses-1_task-ads_beh.tsv`

Biometrics TSV:
- `sub-001_ses-1_biometrics-cmj_biometrics.tsv`

Each data file should have a corresponding JSON sidecar with the same stem.

---

## 5) Derivatives

PRISM supports generating derived variables (scores, subscales) from raw data. These are stored in a BIDS-compliant `derivatives/` folder.

- **Location**: `derivatives/surveys/` or `derivatives/biometrics/`
- **Metadata**: Each derivative dataset must contain its own `dataset_description.json` (BIDS-derivatives requirement). PRISM automatically generates this file, inheriting relevant metadata from the root dataset.
- **Recipes**: Transformations are defined in JSON recipe files. See [DERIVATIVES.md](DERIVATIVES.md) for the full specification.

---

## 6) What is inside a PRISM schema?

PRISM uses JSON Schema documents to define:
- required top-level blocks (commonly `Technical`, `Study`, `Metadata`)
- required fields and allowed types
- optional blocks like `I18n` and `Scoring`

The `Study` block now supports comprehensive metadata including:
- `Authors`, `DOI`, `Citation`
- `Construct`, `Keywords`
- `Reliability`, `Validity`
- `Instructions`

Many of these fields support **i18n objects** (e.g., `{"de": "...", "en": "..."}`) to allow for multi-language documentation.

Schemas live in `schemas/<version>/`.

---

## 7) Detailed Schema Keys

PRISM schemas are organized into logical blocks. Below are the most important keys for `survey` and `biometrics` modalities.

### Technical Block
Contains technical metadata about the data collection.

- `SoftwarePlatform`: Software used (e.g., LimeSurvey, REDCap, My Jump Lab).
- `SoftwareVersion`: Version of the collection software.
- `Language`: Primary language of the assessment (e.g., `en`, `de-AT`).
- `Respondent`: Who provided the data (`self`, `clinician`, `parent`, etc.).
- `AdministrationMethod`: How it was administered (`online`, `paper`, `interview`).
- `Equipment`: Name of the hardware used (e.g., `Stopwatch`, `Dynamometer`).
- `Supervisor`: Who supervised the test (`investigator`, `physician`, `self`).
- `Location`: Where it took place (`laboratory`, `clinic`, `home`).

### Study Block
Contains scientific and bibliographic metadata.

- `OriginalName`: Full canonical name of the instrument.
- `ShortName`: Common abbreviation (e.g., `BDI-II`).
- `Authors`: List of authors.
- `DOI` / `Citation`: Bibliographic references.
- `License` / `LicenseID` / `CopyrightHolder`: Legal and usage information.
- `Construct`: Psychological construct measured (e.g., `depression`).
- `Reliability` / `Validity`: Psychometric properties.
- `AdministrationTime`: Estimated time to complete.
- `References`: Structured list of related papers (manuals, validations); each entry includes `Type`, `Citation`, canonical `DOI` (`10.x/...`), optional `URL`, `Year`, and `Notes`.

### Scoring Block
Defines how the data should be interpreted or scored.

- `ScoringMethod`: General method (e.g., `sum`, `mean`).
- `ScoreRange`: Possible min/max scores.
- `Cutoffs`: Clinical thresholds and their interpretations.
- `ReverseCodedItems`: List of items that need inversion.
- `Subscales`: Structured definitions of sub-scores (Name, Items, Method).

### Item-Level Properties (Columns)
Each column in the TSV can have detailed metadata in the JSON sidecar.

- `Description`: The exact question text or metric description.
- `Levels`: Mapping of numeric values to labels (e.g., `{"0": "Never", "1": "Always"}`).
- `Unit`: Unit of measurement (e.g., `ms`, `cm`, `score`).
- `MinValue` / `MaxValue`: Hard bounds for validation.
- `WarnMinValue` / `WarnMaxValue`: Soft bounds (triggers warnings).
- `Relevance`: Logic for when this item is applicable (e.g., `Q01 == 1`).
- `DataType`: Expected type (`string`, `integer`, `float`).
- `SessionHint` / `RunHint`: Used for longitudinal/repeated data mapping.

Example (Biometrics schema path):
- `schemas/stable/biometrics.schema.json`

---

## 6) Internationalization (i18n)

Some PRISM templates support bilingual/multilingual text fields (e.g., English + German). Depending on the schema, a descriptive field may be either:
- a plain string, or
- a language map like:

```json
{
  "en": "Measures explosive leg power.",
  "de": "Misst die explosive Beinkraft."
}
```

This is especially useful for:
- `Study.Description`
- variable-level `Description`

---

## 7) Detailed modality specifications

PRISM’s modality-specific specifications are documented under `docs/specs/`.

Start here:
- [Biometrics specification](specs/biometrics)
- [Survey specification](specs/survey)
- [Events specification](specs/events)

(These pages are intended to play the same role as BIDS specification pages: they describe the expected files, naming, and metadata semantics.)
