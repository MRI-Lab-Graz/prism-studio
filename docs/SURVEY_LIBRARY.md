# Survey Library & Workflow

The **Survey Library** is a centralized repository for "Golden Master" questionnaire templates. It ensures consistency across studies by providing a single source of truth for survey definitions (questions, scales, metadata).

## Library Location

Surveys are stored in `official/library/survey/` with a unified naming convention:

```
official/library/
└── survey/
    ├── survey-phq9.json       # Patient Health Questionnaire
    ├── survey-gad7.json       # Generalized Anxiety Disorder
    ├── survey-pss10.json      # Perceived Stress Scale
    ├── survey-who5.json       # WHO Well-Being Index
    ├── survey-rosenberg.json  # Demo Self-Esteem Scale
    ├── survey-ads.json        # Allgemeine Depressionsskala
    ├── survey-maia.json       # Multidimensional Interoception
    ├── survey-zkpq.json       # Zuckerman-Kuhlman Personality
    └── ...                    # 100+ validated instruments
```

## Bilingual Templates (i18n)

Surveys now support **bilingual templates** with both German and English in a single JSON file. This eliminates duplication and simplifies maintenance.

### Template Format

Library survey templates use language maps for study metadata and item text:

```json
{
  "Study": {
    "OriginalName": {"de": "Fragebogen zur Gesundheit", "en": "Patient Health Questionnaire"},
    "Authors": ["Spitzer, R. L.", "Kroenke, K.", "Williams, J. B."],
    "DOI": "https://doi.org/10.1046/j.1525-1497.1999.06299.x",
    "Construct": {"de": "Depression", "en": "Depression"},
    "Reliability": {"de": "Cronbachs Alpha = 0.89", "en": "Cronbach's alpha = 0.89"},
    "Instructions": {"de": "…", "en": "…"}
  },
  "PHQ01": {
    "Description": {
      "de": "Wenig Interesse oder Freude an Tätigkeiten",
      "en": "Little interest or pleasure in doing things"
    },
    "Levels": {
      "0": {"de": "Überhaupt nicht", "en": "Not at all"},
      "1": {"de": "An einzelnen Tagen", "en": "Several days"}
    }
  }
}
```

**Discrete vs. numeric scales**
- Use `Levels` for categorical/ordinal responses where only listed values are valid (e.g., Likert options or named categories).
- Use `MinValue` / `MaxValue` for numeric ranges; any value inside the range is valid even if not explicitly listed in `Levels`.
- Do not mix `Levels` with `MinValue` / `MaxValue` for the same item unless the `Levels` entries are just labels for the endpoints; the validator will prioritize the numeric range and emit a warning when both are present.

### Building Language-Specific Versions

Use `prism_tools.py` to compile a clean, single-language output:

```bash
# German version
python prism_tools.py survey i18n-build official/library/survey/survey-phq9.json --lang de

# English version
python prism_tools.py survey i18n-build official/library/survey/survey-phq9.json --lang en
```

### Migrating Existing Surveys

Convert a single-language survey to the bilingual format:

```bash
python prism_tools.py survey i18n-migrate \
  --input official/library/survey/survey-ads.json \
  --output official/library/survey/survey-ads.json

## Metadata harvesting (Open Test Archive / Testarchiv)

Some public registries (e.g., https://www.testarchiv.eu/) provide a rich set of **instrument metadata** (authors, DOI, license, reliability/validity notes, item count, subscales, etc.).

PRISM Studio can ingest this **metadata** into the library to support:
- manuscript boilerplate generation
- discoverability/search
- consistent citation and provenance

Important: this harvesting is intentionally **metadata-only**.
- Do not automatically copy questionnaire item texts or full manuals into PRISM unless the license explicitly allows redistribution and your usage complies with the registry’s terms.
- Many instruments are distributed with restrictions (e.g., `CC BY-NC-ND`), which usually makes “turning the test into a modified JSON template” a derivative work.

Script:

```bash
python scripts/harvest_testarchiv.py \
  --url https://www.testarchiv.eu/de/test/9006565 \
  --auto-en \
  --out survey_library
```

This writes a PRISM-shaped `survey-*.json` template with filled `Study` metadata, but without item variables.
```

## Workflow Overview

The library operates on a **Draft & Publish** model, similar to Git, to prevent accidental changes to production templates.

### 1. Golden Masters (Read-Only)
*   Files in `official/library/survey/` are **Golden Masters**.
*   They are **read-only** and cannot be edited directly.
*   These files represent the approved, validated versions of questionnaires.

### 2. Checkout & Edit (Drafts)
*   To make changes, you must **Checkout** a survey.
*   This creates a copy in the `official/library/survey/drafts/` folder.
*   You can edit the draft using the built-in **Simple Editor** (GUI) or the **Advanced JSON Editor**.
*   The editor supports:
    *   **Metadata**: Description, Units, Data Type.
    *   **Ranges**: Absolute Min/Max and "Normal" (Warning) Min/Max.
    *   **Questions**: Adding, removing, and reordering items.

### 3. Validation & Submission
*   When your edits are complete, click **Submit**.
*   **Automated Validation**: The system checks your draft against the entire library to ensure **variable uniqueness**.
    *   *Example*: If you define a variable `age` that already exists in another survey with a different definition, the submission is blocked.
*   **Merge Request**: If validation passes, the draft is moved to `official/library/survey/merge_requests/`.
*   A repository maintainer must then review and manually move the file to the root folder to update the Golden Master.

## Available Surveys

| Survey | Full Name | Languages |
|--------|-----------|-----------|
| DEMO-9 | Patient Health Questionnaire | DE + EN ✅ |
| DEMO-A7 | Generalized Anxiety Disorder | DE + EN ✅ |
| PSS-10 | Perceived Stress Scale | DE + EN ✅ |
| DEMO-5 | WHO Well-Being Index | DE + EN ✅ |
| Demo Self-Esteem | Self-Esteem Scale | DE + EN ✅ |
| ADS | Allgemeine Depressionsskala | DE (EN placeholder) |
| MAIA | Multidimensional Interoception | DE (EN placeholder) |
| SLEEPDEMO | Demo Sleep Index | DE (EN placeholder) |

## Web Interface

The Survey Library is fully integrated into the PRISM web interface:

1.  **Library Dashboard**: View all surveys, their status (Live/Draft), and perform actions (Checkout, Edit, Submit).
2.  **Editor**: A user-friendly form-based editor for modifying survey content.
3.  **Survey Export**: Select multiple questionnaires from the library and export them as a single LimeSurvey (`.lss`) file for data collection.

## Library Maintenance

To keep the library files up-to-date with the latest PRISM schema (e.g., adding new metadata fields like scoring or normative data), you can use the maintenance script:

```bash
# Fill missing metadata keys in library files from schema
python scripts/fill_missing_metadata.py --modality survey --path official/library/survey
```

This script adds missing keys as empty placeholders, making it easy to see what additional information can be provided for each instrument.

## Multi-Variant Templates

Some questionnaires have multiple validated forms (long vs. short, different response scales). PRISM supports these in a single template file using `Study.Versions` and `Study.VariantDefinitions`.

→ See [Survey Version Planning by Session and Run](SURVEY_VERSION_PLAN.md) for how to configure which variant a project uses at each session and run.
