# Survey Templates

This page explains how survey templates work in PRISM — what they are, how they are structured, where they live, and how to create or extend them.

---

## What Is a Survey Template?

A **survey template** is a JSON sidecar file that defines the structure and metadata of a questionnaire. Every survey data file (`.tsv`) must have a matching `_survey.json` sidecar. The sidecar does two jobs:

1. **Instrument definition** — item texts, response levels, reverse coding, scoring rules.
2. **Administration record** — how the instrument was actually collected in this dataset (language, platform, respondent, method).

PRISM keeps these two concerns in the same file shape but separates them into dedicated blocks (`Study` vs `Technical`), so validation and downstream tools always know where to look.

---

## Two Contexts: Official Library vs. Project Copy

PRISM uses the **same JSON structure** in two different contexts. It is important to understand the difference:

| | Official library template | Project copy |
|---|---|---|
| **Location** | `official/library/survey/survey-<name>.json` | `code/library/survey/survey-<name>.json` |
| **Purpose** | Canonical instrument definition | Administration record for one dataset |
| **Contains** | Item texts, levels, `Study` metadata, `Scoring` | Same, plus `Technical` administration details |
| **Editable by** | Repository maintainers (via draft/PR workflow) | Researchers (per dataset) |
| **TaskName required?** | No | Yes |

When you add a survey to a project, PRISM copies the official template into `code/library/survey/` and you fill in the `Technical` block to record how you actually ran the study. BIDS apps, validators, and reporting tools only read the project copy.

---

## Template Structure

### Minimal valid template (data already collected, no official library entry)

```json
{
  "Metadata": {
    "SchemaVersion": "1.1.1",
    "CreationDate": "2026-01-15"
  },
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "Language": "en",
    "Respondent": "self"
  },
  "Study": {
    "TaskName": "mymeasure",
    "OriginalName": "My Custom Measure"
  },
  "MM01": {
    "Description": "How are you feeling right now?"
  }
}
```

### Full example with i18n, scoring, and administration details

```json
{
  "Metadata": {
    "SchemaVersion": "1.1.1",
    "CreationDate": "2026-03-01"
  },
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "Language": "de",
    "Respondent": "self",
    "AdministrationMethod": "online",
    "SoftwarePlatform": "LimeSurvey",
    "SoftwareVersion": "6.3"
  },
  "I18n": {
    "Languages": ["en", "de"],
    "DefaultLanguage": "de",
    "TranslationMethod": "forward-backward"
  },
  "Study": {
    "TaskName": "pss",
    "OriginalName": {
      "en": "Perceived Stress Scale",
      "de": "Wahrgenommene Stressskala"
    },
    "ShortName": "PSS-10",
    "Authors": ["Cohen, S.", "Kamarck, T.", "Mermelstein, R."],
    "Year": 1983,
    "DOI": "https://doi.org/10.2307/2136404",
    "LicenseID": "CC-BY-4.0",
    "ItemCount": 10,
    "Instructions": {
      "en": "The questions ask about your feelings and thoughts during the LAST MONTH.",
      "de": "Die Fragen beziehen sich auf Ihre Gefühle und Gedanken im LETZTEN MONAT."
    }
  },
  "Scoring": {
    "ScoringMethod": "sum",
    "ScoreRange": {"min": 0, "max": 40},
    "ReverseCodedItems": ["PSS04", "PSS05", "PSS07", "PSS08"]
  },
  "PSS01": {
    "Description": {
      "en": "Been upset because of something that happened unexpectedly?",
      "de": "Über etwas aufgewühlt, das unerwartet passiert ist?"
    },
    "Levels": {
      "0": {"en": "Never", "de": "Nie"},
      "1": {"en": "Almost never", "de": "Fast nie"},
      "2": {"en": "Sometimes", "de": "Manchmal"},
      "3": {"en": "Fairly often", "de": "Öfters"},
      "4": {"en": "Very often", "de": "Sehr oft"}
    }
  }
}
```

---

## Key Fields Reference

### `Study` block

| Field | Type | Description |
|---|---|---|
| `TaskName` | string | **Required in project copies.** The short identifier used in filenames (e.g., `pss` matches `survey-pss.json`). |
| `OriginalName` | string \| i18n object | **Required.** Full canonical name of the instrument. |
| `ShortName` | string \| i18n object | Common abbreviation (e.g., `PSS-10`). Replaces legacy `Abbreviation`. |
| `Authors` | array | List of instrument authors. |
| `Year` | integer | Publication year (1900–2100). |
| `DOI` | string | Digital Object Identifier (`10.x/…` or full URL). |
| `Citation` | string | Formatted citation string. |
| `LicenseID` | string | SPDX license identifier (e.g., `CC-BY-4.0`, `Proprietary`). |
| `License` | string \| i18n object | License terms in plain text. |
| `Source` | string | URL to the instrument's original source. |
| `ItemCount` | integer | Total number of items. Replaces legacy `NumberOfItems`. |
| `Instructions` | string \| i18n object | Instructions shown to participants. |
| `Construct` | string \| i18n object | Psychological construct measured (e.g., `depression`). |
| `Description` | string \| i18n object | Instrument description or abstract. |
| `Versions` | object | Named variants of the instrument (see [survey versioning](SURVEY_VERSION_PLAN.md)). |

> **Backward compatibility:** `Abbreviation` is still accepted as a synonym for `ShortName`, and `NumberOfItems` for `ItemCount`. Official library templates use the canonical names. Project-local templates that have not yet been migrated continue to work.

### `Technical` block

| Field | Required | Description |
|---|---|---|
| `StimulusType` | **Yes** | Always `"Questionnaire"`. |
| `FileFormat` | **Yes** | Always `"tsv"`. |
| `Language` | **Yes** | BCP-47 language code actually administered (e.g., `en`, `de-AT`). |
| `Respondent` | **Yes** | Who filled it in: `self`, `parent`, `clinician`, etc. |
| `AdministrationMethod` | Recommended | `online`, `paper`, `interview`, `phone`, `mixed`. |
| `SoftwarePlatform` | Recommended | Software used: `LimeSurvey`, `PsychoPy`, `Pavlovia`, `Paper and Pencil`, etc. |
| `SoftwareVersion` | Optional | Version of the software platform. |
| `ResponseType` | Optional | Input modality: `["button"]`, `["slider"]`, `["keyboard"]`. |

### `I18n` block (optional)

| Field | Description |
|---|---|
| `Languages` | List of BCP-47 codes available in the template (e.g., `["en", "de"]`). |
| `DefaultLanguage` | Which language to use when compiling or exporting (e.g., `en`). |
| `TranslationMethod` | Translation/validation approach (e.g., `forward-backward`). |

### Item definitions

Every top-level key that is not `Study`, `Technical`, `Metadata`, `I18n`, or `Scoring` is treated as an item (question). Items use uppercase codes with a numeric suffix, e.g. `PSS01`.

| Field | Required | Description |
|---|---|---|
| `Description` | **Yes** | Question text. String or i18n object. |
| `Levels` | No | Response options as `{"0": "label", "1": "label", …}`. Values can be i18n objects. |
| `MinValue` / `MaxValue` | No | Numeric bounds. Use instead of `Levels` for continuous or slider responses. |
| `Reversed` | No | `true` if item is reverse-coded (used by scorer). |
| `DataType` | No | `string`, `integer`, or `float`. |
| `TermURL` | No | Ontology URI for the measured concept. |
| `Relevance` | No | Conditional display logic (e.g., `Q01 == 1`). |

---

## Creating a New Template

### Option A — Excel import (recommended for new instruments)

The fastest way. Use the Excel template:

```
examles/excel_import/survey_import_example.xlsx
```

Fill in the **`General`** sheet with survey-level metadata (one row per field), and the **`Items`** sheet with one row per question. Then import via PRISM Studio → Tools → Import Survey.

Key columns in `Items`:

| Column | Description |
|---|---|
| `ItemID` | Unique item code (e.g., `PSS01`) |
| `Description` / `Description_de` / `Description_en` | Item text (language suffix optional) |
| `Scale` / `Scale_de` / `Scale_en` | Response scale labels, pipe-separated: `0=Never\|1=Sometimes` |
| `MinValue` / `MaxValue` | Numeric bounds for open-ended items |
| `Session` / `Run` | Marks items specific to a session/run |

Key rows in `General`:

| Field | Description |
|---|---|
| `OriginalName_en` / `OriginalName_de` | Full instrument name per language |
| `ShortName` | Common abbreviation |
| `Authors` | Author list (semicolon-separated) |
| `DOI` | DOI string |
| `Citation` | APA-style citation |
| `I18nLanguages` | Space- or comma-separated language codes (e.g., `en de`) |
| `I18nDefaultLanguage` | Default export language (e.g., `en`) |
| `Instructions_en` / `Instructions_de` | Participant instructions per language |
| `AdministrationMethod` | `online`, `paper`, … |
| `SoftwarePlatform` | e.g., `LimeSurvey` |

### Option B — JSON directly

Write the JSON by hand or copy an existing official template:

```bash
cp official/library/survey/survey-pss.json official/library/survey/survey-myinstrument.json
# Edit Study metadata and item codes
```

Validate immediately:

```bash
python app/prism.py --validate-templates official/library/survey/
```

### Option C — Web interface template editor

PRISM Studio provides a form-based editor under **Tools → Template Editor**. It lets you add/edit items, set metadata, and save without touching JSON directly.

---

## Official Library

The 110+ templates in `official/library/survey/` are the canonical PRISM instrument library. They are read-only "golden masters":

- Cannot be edited directly — go through the **Checkout → Edit → Submit** workflow.
- Checked out copies land in `official/library/survey/drafts/`.
- Merged copies replace the golden master after review.

All official templates use canonical field names: `ShortName` (not `Abbreviation`) and `ItemCount` (not `NumberOfItems`).

Browse them by instrument name in PRISM Studio → Tools → Survey Library, or directly in `official/library/survey/`.

---

## Validation

Run the template validator at any time:

```bash
# Validate the full official library
python app/prism.py --validate-templates official/library/survey/

# Validate project-local templates
python app/prism.py --validate-templates code/library/survey/
```

Common errors and fixes:

| Error | Fix |
|---|---|
| `Study.OriginalName is missing` | Add `OriginalName` to the `Study` block. |
| `Study.TaskName is missing` | Required in project copies — add the task identifier. |
| `Item ITEM01 missing Description` | Every item must have a `Description` field. |
| `Study.Year seems incorrect` | Check the year value (expected 1900–2100). |
| `Study.DOI should start with '10.'` | Use format `10.xxxx/…` or full `https://doi.org/…`. |
| `Study.ItemCount must be an integer` | Set `ItemCount` to a whole number, not a string. |

---

## LimeSurvey Export

Templates in the official library or project library can be exported directly to LimeSurvey (`.lss` or `.lsa` format) via **Tools → Export to LimeSurvey**. The exporter reads `ShortName`, `OriginalName`, `Authors`, `DOI`, and `Citation` to populate the LimeSurvey survey description block automatically.

For i18n templates, specify the export language. The compiled output contains only that language's text.

---

## Related Pages

- [Survey Specification](specs/survey.md) — full field-by-field schema reference
- [Template Validation](TEMPLATE_VALIDATION.md) — validation rules and error messages
- [Survey Library](SURVEY_LIBRARY.md) — library management and workflow
- [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) — export workflow details
- [Recipes & Scoring](RECIPES.md) — how scoring is defined separately from templates
- [Survey Versioning](SURVEY_VERSION_PLAN.md) — template `Study.Version` and `acq-<version>`
