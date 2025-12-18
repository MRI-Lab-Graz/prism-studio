# Survey Library & Workflow

The **Survey Library** is a centralized repository for "Golden Master" questionnaire templates. It ensures consistency across studies by providing a single source of truth for survey definitions (questions, scales, metadata).

## Library Location

Surveys are stored in `library/survey/` with a unified naming convention:

```
library/
└── survey/
    ├── survey-phq9.json       # Patient Health Questionnaire
    ├── survey-gad7.json       # Generalized Anxiety Disorder
    ├── survey-pss10.json      # Perceived Stress Scale
    ├── survey-who5.json       # WHO Well-Being Index
    ├── survey-rosenberg.json  # Rosenberg Self-Esteem Scale
    ├── survey-ads.json        # Allgemeine Depressionsskala
    ├── survey-maia.json       # Multidimensional Interoception
    ├── survey-psqi.json       # Pittsburgh Sleep Quality Index
    └── ...
```

## Bilingual Templates (i18n)

Surveys now support **bilingual templates** with both German and English in a single JSON file. This eliminates duplication and simplifies maintenance.

### Template Format

Each item contains language-specific keys:

```json
{
  "Study": {
    "OriginalName_de": "Fragebogen zur Gesundheit",
    "OriginalName_en": "Patient Health Questionnaire"
  },
  "Items": {
    "PHQ01": {
      "question_de": "Wenig Interesse oder Freude an Tätigkeiten",
      "question_en": "Little interest or pleasure in doing things",
      "Levels_de": {"0": "Überhaupt nicht", "1": "An einzelnen Tagen", ...},
      "Levels_en": {"0": "Not at all", "1": "Several days", ...}
    }
  }
}
```

### Building Language-Specific Versions

Use `prism_tools.py` to compile a clean, single-language output:

```bash
# German version
python prism_tools.py survey i18n-build library/survey/survey-phq9.json --lang de

# English version
python prism_tools.py survey i18n-build library/survey/survey-phq9.json --lang en
```

### Migrating Existing Surveys

Convert a single-language survey to the bilingual format:

```bash
python prism_tools.py survey i18n-migrate \
  --input library/survey/survey-ads.json \
  --output library/survey/survey-ads.json
```

## Workflow Overview

The library operates on a **Draft & Publish** model, similar to Git, to prevent accidental changes to production templates.

### 1. Golden Masters (Read-Only)
*   Files in `library/survey/` are **Golden Masters**.
*   They are **read-only** and cannot be edited directly.
*   These files represent the approved, validated versions of questionnaires.

### 2. Checkout & Edit (Drafts)
*   To make changes, you must **Checkout** a survey.
*   This creates a copy in the `library/survey/drafts/` folder.
*   You can edit the draft using the built-in **Simple Editor** (GUI) or the **Advanced JSON Editor**.
*   The editor supports:
    *   **Metadata**: Description, Units, Data Type.
    *   **Ranges**: Absolute Min/Max and "Normal" (Warning) Min/Max.
    *   **Questions**: Adding, removing, and reordering items.

### 3. Validation & Submission
*   When your edits are complete, click **Submit**.
*   **Automated Validation**: The system checks your draft against the entire library to ensure **variable uniqueness**.
    *   *Example*: If you define a variable `age` that already exists in another survey with a different definition, the submission is blocked.
*   **Merge Request**: If validation passes, the draft is moved to `library/survey/merge_requests/`.
*   A repository maintainer must then review and manually move the file to the root folder to update the Golden Master.

## Available Surveys

| Survey | Full Name | Languages |
|--------|-----------|-----------|
| PHQ-9 | Patient Health Questionnaire | DE + EN ✅ |
| GAD-7 | Generalized Anxiety Disorder | DE + EN ✅ |
| PSS-10 | Perceived Stress Scale | DE + EN ✅ |
| WHO-5 | WHO Well-Being Index | DE + EN ✅ |
| Rosenberg | Self-Esteem Scale | DE + EN ✅ |
| ADS | Allgemeine Depressionsskala | DE (EN placeholder) |
| MAIA | Multidimensional Interoception | DE (EN placeholder) |
| PSQI | Pittsburgh Sleep Quality Index | DE (EN placeholder) |

## Web Interface

The Survey Library is fully integrated into the Prism-Validator web interface:

1.  **Library Dashboard**: View all surveys, their status (Live/Draft), and perform actions (Checkout, Edit, Submit).
2.  **Editor**: A user-friendly form-based editor for modifying survey content.
3.  **Survey Export**: Select multiple questionnaires from the library and export them as a single LimeSurvey (`.lss`) file for data collection.
