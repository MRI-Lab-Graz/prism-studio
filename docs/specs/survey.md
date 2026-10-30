# Survey

The `survey` modality is a PRISM extension for handling complex questionnaires. It treats surveys as rich data with detailed metadata, rather than simple phenotypic variables.

> [!TIP]
> **Starting a new survey?** The canonical workbook is [official/create_new_survey/survey_import_template.xlsx](https://github.com/MRI-Lab-Graz/prism-studio/raw/main/official/create_new_survey/survey_import_template.xlsx).
> For direct browser download on Read the Docs, you can also use [Survey Import Template](https://github.com/MRI-Lab-Graz/prism-studio/raw/main/docs/examples/survey_import_template.xlsx).
> For a guided, step-by-step walkthrough with worked examples, see
> [Excel Survey Template — Basics](https://prism-studio.readthedocs.io/en/latest/EXCEL_TEMPLATE_BASICS.html) and
> [— Multiple Versions](https://prism-studio.readthedocs.io/en/latest/EXCEL_TEMPLATE_ADVANCED.html) — this page stays the terse
> field-by-field reference.

## Import Template Layout

The Excel import template is split into dedicated sheets:

- `Items`: item-level columns (`ItemID`, `Description`, `Scale`, `Session`, `Run`, etc.)
- `General`: transposed survey-level metadata with `Field` + `Value` rows (`OriginalName_*`, `Version_*`, `Instructions_*`, citation, i18n settings, etc.)
- `Variants` (optional): explicit variant definitions (`Group`, `VariantID`, `ItemCount`, `ScaleType`, `Description_<lang>`)
- `Help`: quick reference for column semantics and examples

The importer merges these sheets automatically.

In `General`, rows marked red in the `Required` column indicate schema-critical metadata entries.

## How To Use The Excel Workbook

Use this workflow when you create or update a survey template from Excel:

1. Start from `official/create_new_survey/survey_import_template.xlsx`.
2. Fill `General` first (instrument-level metadata such as name, version context, respondent, and administration details).
3. Fill `Items` with default/base item definitions (`ItemID`, `Description_*`, and either `Scale_*` or numeric bounds).
4. For single-version surveys, leave `Variants` empty.
5. For multi-version surveys, define available variant IDs in `Variants` and add item-level override rows when scale behavior changes by variant.
6. Use `Items.ApplicableVersions` per item row to scope items to specific variants. For multiple variants, enter plain text lists (for example `10-likert;7-likert`).
7. Keep the `Help` sheet open while editing, then save as `.xlsx` and import with PRISM's survey/template workflow.

The `Items` sheet defines defaults. The `Variants` sheet is optional and is used for explicit variant definitions and variant-specific item overrides.

## Multi-version Template Fields

To define multiple questionnaire variants in one import workbook:

- In `General`, set:
  - `Version` = active/default variant ID
  - `Versions` = semicolon-separated list of all variant IDs (for example `10-likert;7-likert;10-vas`)
- In `Items`, optionally set `ApplicableVersions` per item to restrict items to specific variants.
- In `Variants` (optional), provide explicit variant metadata. If omitted, PRISM infers `VariantDefinitions` from `Versions` and item-level `ApplicableVersions`.

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

`sub-<label>[_ses-<label>]_task-<label>_survey.tsv`

For example: `sub-002_ses-02_task-wellbeing-multi_survey.tsv`. The `task-<label>`
entity identifies the instrument (per `schemas/stable/entities.schema.json`,
the `survey` modality uses suffix `survey` and **requires** the `task` entity: a file name
without `task-<label>` is rejected) — it is not a `survey-<label>` suffix.

*Note: Legacy formats `_task-<label>_beh.tsv` and `_survey-<label>_beh.tsv` are
also recognized for backward compatibility but are not the current convention.*

## Sidecar JSON (`*_survey.json`)

The survey sidecar defines the structure, content, and administrative metadata of the questionnaire.

### Top-Level Objects

| Object | Requirement | Description |
| --- | --- | --- |
| `Technical` | **REQUIRED** | Platform and respondent details. |
| `I18n` | **REQUIRED** | Languages the template contains. |
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
| `SoftwarePlatform` | **REQUIRED** | `string` | Project-local platform used for administration (e.g., `"LimeSurvey"`, `"Paper and Pencil"`). |
| `SoftwareVersion` | OPTIONAL | `string` | Project-local version of the software platform. |
| `Language` | **REQUIRED** | `string` | Language the instrument was originally published in (e.g., `"en"`, `"de-AT"`); a single tag, never empty. |
| `Respondent` | **REQUIRED** | `string` | Project-local respondent type (e.g., `"self"`, `"parent"`). |
| `AdministrationMethod` | **REQUIRED** | `string` | Project-local administration mode (`online`, `paper`, `interview`, `phone`, `mixed`). |
| `ResponseType` | RECOMMENDED | `array` | Input method (e.g., `["button"]`, `["slider"]`). |
| `Equipment` | OPTIONAL | `string` | Hardware used (e.g., `Stopwatch`, `Dynamometer`). |
| `Supervisor` | OPTIONAL | `string` | Who supervised the test (`investigator`, `physician`, `self`). |
| `Location` | OPTIONAL | `string` | Where it took place (`laboratory`, `clinic`, `home`). |

> Note: PRISM supports bilingual (i18n) *source templates* and single-language *compiled* templates. See the i18n section below.

### `I18n` Object

`I18n` is **REQUIRED**. `Languages` declares which languages the template contains (at least one, no duplicates, each a tag like `en` or `de-AT`); every item text is expected in each of them.

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `Languages` | **REQUIRED** | `array` | Languages this template contains; one or more unique codes (e.g., `["en", "de-AT"]`). |
| `DefaultLanguage` | OPTIONAL | `string` | Default language when compiling/exporting; a language code, never empty. |
| `TranslationMethod` | OPTIONAL | `string` | Translation validation approach (e.g., `forward-backward`). |

### `Study` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `TaskName` | **REQUIRED** | `string` | Project-local task identifier (e.g., `"moodcheck"`). |
| `OriginalName` | **REQUIRED** | `string` \| `object` | Full name (e.g., `"Dummy Mood Check"`); not empty. As an object it needs a non-empty `en` entry (see English rule). |
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
| `Help` | OPTIONAL | `string` \| `object` | Help text shown with the question (string or i18n map). |
| `OtherOption` | OPTIONAL | `object` | Adds an "Other, please specify" choice: `{"enabled": true, "label": "Other"}`; `label` is a string or i18n map. |
| `Levels` | OPTIONAL | `object` | Mapping of numeric values to labels. Values may be strings or i18n maps. |
| `Unit` / `Units` | OPTIONAL | `string` | Units (if applicable). |
| `TermURL` | OPTIONAL | `string` | URL to an ontology term. |
| `Relevance` | OPTIONAL | `string` | Logic for when this item is applicable (e.g., `Q01 == 1`). |
| `MinValue` / `MaxValue` | OPTIONAL | `number` | Hard bounds for validation. |
| `WarnMinValue` / `WarnMaxValue` | OPTIONAL | `number` | Soft bounds (triggers warnings). |
| `AllowedValues` | OPTIONAL | `array` | List of allowed values. |
| `DataType` | OPTIONAL | `string` | Expected type (`string`, `integer`, `float`). |
| `SessionHint` / `RunHint` | OPTIONAL | `string` | Used for longitudinal/repeated data mapping. |

**Required fields are filled.** An empty string never counts as a value: `Technical.*`, `Study.TaskName`, `Study.Citation`, `Study.OriginalName` and `Metadata.Creator` must be non-empty, and the enums of `StimulusType`, `FileFormat`, `SoftwarePlatform`, `Respondent` and `AdministrationMethod` do not list `""`.

**English rule.** Every text field of `Study` that takes a language object (`OriginalName`, `Description`, `Instructions`, `Construct`, `License`, `Reliability`, `Validity`, `Norming`, `PermissionsNote`, `Translation.Notes`, `References[].Notes`, `VariantDefinitions[].Description`) must carry a non-empty `en` entry when written as an object; a plain string is always fine and other languages are optional additions. `ShortName` and `Version` are free.

### `Metadata` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `SchemaVersion` | **REQUIRED** | `string` | Schema version the file was written for (`major.minor.patch`). |
| `CreationDate` | **REQUIRED** | `string` | Date of creation (`YYYY-MM-DD`). |
| `Creator` | **REQUIRED** | `string` | Who built this template (official library: `PRISM Studio`); not empty. |

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
    "SchemaVersion": "2.0.0",
    "CreationDate": "2025-01-01",
    "Creator": "PRISM Studio"
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

<!-- BEGIN SCHEMA REFERENCE (generated by scripts/generate_schema_reference.py; do not edit) -->

## Field reference (`survey.schema.json`, version 2.0.0)

Generated from [`schemas/stable/survey.schema.json`](../../app/schemas/stable/survey.schema.json). Nested fields are shown as `Block.Field`; `[]` marks list items. *Required* applies within its parent block.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `Technical` | object | yes | Technical survey properties |
| `Technical.StimulusType` | string | yes | Must be 'Questionnaire' for survey data Allowed: `Questionnaire`. |
| `Technical.FileFormat` | string | yes | Survey data file format Allowed: `tsv`. |
| `Technical.SoftwarePlatform` | string | yes | Software platform used for data collection (LimeSurvey, PsychoPy, Pavlovia, Paper and Pencil, etc.) Allowed: `LimeSurvey`, `PsychoPy`, `Pavlovia`, `Paper and Pencil`, `Other`. |
| `Technical.SoftwareVersion` | string | no | Version of the survey software platform (not required for Paper and Pencil) |
| `Technical.Language` | string | yes | Language the instrument was originally published in |
| `Technical.Respondent` | string | yes | Who provided the responses Allowed: `self`, `clinician`, `parent`, `teacher`, `caregiver`, `other`. |
| `Technical.AdministrationMethod` | string | yes | How the survey was administered Allowed: `online`, `paper`, `interview`, `phone`, `mixed`. |
| `I18n` | object | yes | Internationalization settings for multi-language surveys |
| `I18n.Languages` | array | yes | Languages this template contains; every item text is expected in each of them |
| `I18n.DefaultLanguage` | string | no | Default/primary language of the instrument |
| `I18n.TranslationMethod` | string | no | Method used for translation validation Allowed: `forward-backward`, `committee`, `parallel`, `original`, `validated-translation`, ``. |
| `Study` | object | yes | Study-specific survey parameters |
| `Study.TaskName` | string | yes | Short task identifier matching filename (e.g., bdi, phq9, bfi-s) |
| `Study.OriginalName` | string / object | yes | Full canonical name of the instrument (e.g., Beck Depression Inventory) |
| `Study.OriginalName.en` | string | yes |  |
| `Study.ShortName` | string / object | no | Common abbreviation (e.g., BDI-II, PHQ-9) |
| `Study.Version` | string / object | no | Version of the instrument (e.g., II, 5.0, 21-item) |
| `Study.Versions` | array | no | List of available versions/forms of this instrument (e.g., ['short', 'long', 'screening']). Use when the same instrument has multiple validated forms with diff… |
| `Study.VariantDefinitions` | array | no | Structured definitions for concrete instrument variants that combine form length and response format (e.g., 10-item Likert, 7-item Likert, 10-item VAS). Use wi… |
| `Study.VariantDefinitions[].VariantID` | string | yes | Identifier for this concrete variant (e.g., 10item-likert5, 10item-vas100). |
| `Study.VariantDefinitions[].ItemCount` | integer / null | no | Number of items expected in this variant. |
| `Study.VariantDefinitions[].ScaleType` | string | no | Primary response scale family used in this variant. Allowed: `likert`, `vas`, `visual-analogue`, `categorical`, `binary`, `free-text`, `other`, ``. |
| `Study.VariantDefinitions[].Description` | string / object | no | Optional description of this variant. |
| `Study.VariantDefinitions[].Description.en` | string | yes |  |
| `Study.Authors` | array | no | Authors of the instrument |
| `Study.Citation` | string | yes | DOI or citation for the instrument |
| `Study.DOI` | string | no | Digital Object Identifier (DOI) for the instrument; use the canonical DOI string (10.x/...) without protocol prefixes or leave empty when unavailable |
| `Study.License` | string / object | no | License statement for this instrument as provided by the source registry |
| `Study.License.en` | string | yes |  |
| `Study.LicenseID` | string | yes | Normalized license identifier (prefer SPDX or Creative Commons identifiers) Allowed: `CC-BY-4.0`, `CC-BY-SA-4.0`, `CC-BY-ND-4.0`, `CC-BY-NC-4.0`, `CC-BY-NC-SA-4.0`, `CC-BY-NC-ND-4.0`, `MIT`, `Apache-2.0`, `GPL-3.0-only`, `GPL-3.0-or-later`, `LGPL-3.0-only`, `BSD-3-Clause`, `Unlicense`, `PDDL-1.0`, `CC0-1.0`, `Proprietary`, `Other`. |
| `Study.Category` | string | yes | Content-domain category for official library instruments (mandatory for official/library/survey templates only; see x-prism.officialOnlyRequired) Allowed: `Personality & Individual Differences`, `Mood, Anxiety & Clinical Screening`, `Well-being & Life Satisfaction`, `Social, Relationships & Attachment`, `Addictive & Problematic Behaviors`, `Self-Concept & Self-Esteem`, `Aggression, Antisocial & Dark Traits`, `Cognitive & Executive Function`, `Autism & Neurodevelopmental`, `Sleep, Health & Physical`, `Beliefs, Values & Worldview`, `Educational & Occupational`, `Other / Uncategorized`. |
| `Study.LicenseURL` | string | no | License URL when available (e.g., creativecommons.org link) |
| `Study.CopyrightHolder` | string | no | Rights holder for the instrument (e.g., publisher, author group) |
| `Study.Access` | string | no | High-level access/permission classification for transparency Allowed: `public`, `permission-required`, `licensed`, `unknown`, ``. |
| `Study.PermissionsNote` | string / object | no | Short note describing permissions/usage constraints |
| `Study.PermissionsNote.en` | string | yes |  |
| `Study.PermissionsURL` | string | no | URL to permission statement or licensing portal |
| `Study.TermURL` | string | no | URL to formal definition (e.g., PhenX, SNOMED) |
| `Study.Construct` | string / object | no | Primary psychological construct measured (e.g., depression, anxiety, stress) |
| `Study.Construct.en` | string | yes |  |
| `Study.Keywords` | array | no | Keywords describing the instrument |
| `Study.Description` | string / object | no | Detailed description or abstract of the instrument |
| `Study.Description.en` | string | yes |  |
| `Study.Instructions` | string / object | no | Instructions given to the participant |
| `Study.Instructions.en` | string | yes |  |
| `Study.Reliability` | string / object | no | Information about the reliability of the instrument |
| `Study.Reliability.en` | string | yes |  |
| `Study.Validity` | string / object | no | Information about the validity of the instrument |
| `Study.Validity.en` | string | yes |  |
| `Study.Subscales` | array | no | List of subscale names if applicable |
| `Study.ItemCount` | integer / null | no | Number of items in the instrument |
| `Study.AgeRange` | object / string | no | Target age range for the instrument in years |
| `Study.AgeRange.min` | number | yes | Minimum age in years |
| `Study.AgeRange.max` | number | yes | Maximum age in years |
| `Study.AdministrationTime` | object / string | no | Estimated time to complete the instrument in minutes |
| `Study.AdministrationTime.min` | number | yes | Minimum estimated minutes |
| `Study.AdministrationTime.max` | number | yes | Maximum estimated minutes |
| `Study.ScoringTime` | object / string | no | Estimated time to score the instrument in minutes |
| `Study.ScoringTime.min` | number | yes | Minimum estimated minutes |
| `Study.ScoringTime.max` | number | yes | Maximum estimated minutes |
| `Study.Norming` | string / object | no | Information about the norming of the instrument |
| `Study.Norming.en` | string | yes |  |
| `Study.References` | array | no | Structured reference list for the instrument (primary paper, manual, translation, norms, validation, etc.) |
| `Study.References[].Type` | string | yes | Reference type Allowed: `primary`, `manual`, `translation`, `validation`, `norms`, `other`, ``. |
| `Study.References[].Citation` | string | no | Human-readable citation |
| `Study.References[].DOI` | string | no | DOI for the reference (canonical 10.x/... string) or empty when unavailable |
| `Study.References[].URL` | string | no | URL for the reference |
| `Study.References[].Year` | integer / null | no | Publication year |
| `Study.References[].Notes` | string / object | no | Optional notes about the reference |
| `Study.References[].Notes.en` | string | yes |  |
| `Study.Translation` | object | no | Translation/adaptation provenance (especially for non-original language versions) |
| `Study.Translation.SourceLanguage` | string | no | Source language of the instrument |
| `Study.Translation.TargetLanguage` | string | no | Target language used in this dataset |
| `Study.Translation.Validated` | boolean | no | Whether this translation/adaptation is validated |
| `Study.Translation.Method` | string | no | Translation/adaptation method (if different from I18n.TranslationMethod) |
| `Study.Translation.Reference` | string | no | Citation/DOI/URL for the translation/adaptation reference |
| `Study.Translation.Notes` | string / object | no | Additional provenance notes |
| `Study.Translation.Notes.en` | string | yes |  |
| `Normative` | object | no | Normative data and reference values |
| `Normative.ReferencePopulation` | string | no | Population on which normative data is based |
| `Normative.ReferenceSource` | string | no | Citation for normative data |
| `Normative.Percentiles` | object | no | Percentile cutoffs (e.g., {'p25': 10, 'p50': 15, 'p75': 20}) |
| `Metadata` | object | yes | Administrative metadata |
| `Metadata.SchemaVersion` | string | yes |  |
| `Metadata.CreationDate` | string | yes | Date of creation |
| `Metadata.Creator` | string | yes | Who built this template (official library: PRISM Studio) |

<!-- END SCHEMA REFERENCE -->
