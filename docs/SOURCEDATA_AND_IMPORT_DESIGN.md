# PRISM Sourcedata and Import System Design

## Overview

This document defines the structure and workflow for handling raw source data, import manifests, and template management in PRISM Studio.

## Design Principles

1. **Expert in the loop** - User confirms all automated detections and merges
2. **Full provenance** - Track where every piece of data and every template came from
3. **Flexible but guided** - Handle non-standard naming, but recommend conventions
4. **Reproducible** - Import manifests document exactly how data was converted

---

## 1. Sourcedata Structure

```
sourcedata/
├── README.md                         # Explains structure and usage
│
├── raw/                              # Original untouched data files
│   ├── limesurvey/
│   │   ├── study_export_2024-01-15.lsa
│   │   └── study_export_2024-06-20.lsa
│   ├── excel/
│   │   └── biometrics_batch1.xlsx
│   ├── csv/
│   │   └── external_survey.csv
│   └── other/
│       └── redcap_export.csv
│
├── structure/                        # Survey structure definitions (no response data)
│   ├── limesurvey/
│   │   ├── my_study_survey.lss       # LimeSurvey structure export
│   │   └── followup_survey.lss
│   └── prism/
│       └── custom_questionnaire.json # PRISM-native template
│
└── imports/                          # Import manifests (conversion records)
    ├── 2024-01-20_baseline.json
    ├── 2024-06-25_followup.json
    └── README.md                     # Explains manifest format
```

### Folder Purposes

| Folder | Purpose | File Types |
|--------|---------|------------|
| `raw/` | Original data exports, never modified | .lsa, .xlsx, .csv |
| `structure/` | Survey definitions without response data | .lss, .json |
| `imports/` | Records of how data was converted | .json manifests |

---

## 2. Import Manifest Specification

Each import creates a manifest documenting exactly what was done.

### Manifest Schema

```json
{
  "$schema": "https://prism-studio.org/schemas/import-manifest.json",
  "manifest_version": "1.0",

  "import_id": "2024-01-20_baseline",
  "created": "2024-01-20T14:30:00Z",
  "created_by": "user@example.com",
  "description": "Baseline data collection import",

  "source_files": [
    {
      "path": "raw/limesurvey/study_export_2024-01-15.lsa",
      "type": "limesurvey_archive",
      "sha256": "abc123...",
      "original_filename": "survey_export.lsa",
      "archived_date": "2024-01-20T14:30:00Z"
    }
  ],

  "target_session": "ses-01",

  "participant_mapping": {
    "id_column": "participant_id",
    "id_pattern": "^P\\d{3}$",
    "transform": "P{id:03d} -> sub-{id:03d}"
  },

  "questionnaire_mappings": [
    {
      "detected_prefix": "phq9_",
      "matched_template": "library/survey/survey-phq9.json",
      "match_confidence": 0.95,
      "user_confirmed": true,
      "instance": null,
      "output_task": "phq9",
      "output_file": "sub-{id}/ses-01/survey/sub-{id}_ses-01_task-phq9_beh.tsv"
    },
    {
      "detected_prefix": "phq9post_",
      "matched_template": "library/survey/survey-phq9.json",
      "match_confidence": 0.90,
      "user_confirmed": true,
      "instance": "post",
      "output_task": "phq9post",
      "output_file": "sub-{id}/ses-01/survey/sub-{id}_ses-01_task-phq9post_beh.tsv",
      "notes": "Post-intervention PHQ-9 administration"
    }
  ],

  "participants_imported": ["sub-001", "sub-002", "sub-003"],
  "participants_skipped": [],
  "warnings": [],
  "errors": []
}
```

### Key Fields Explained

| Field | Purpose |
|-------|---------|
| `source_files[].sha256` | Verify file hasn't changed |
| `match_confidence` | How certain the auto-detection was |
| `user_confirmed` | User explicitly confirmed this mapping |
| `instance` | For same questionnaire used multiple times |

---

## 3. Template JSON Schema with Provenance

Templates should track their full lineage.

### Enhanced Template Schema

```json
{
  "$schema": "https://prism-studio.org/schemas/survey-template.json",
  "schema_version": "1.0",

  "template_id": "phq9",
  "name": "Patient Health Questionnaire-9",
  "short_name": "PHQ-9",
  "version": "1.0",

  "provenance": {
    "source_type": "published_instrument",
    "citation": {
      "authors": ["Kroenke K", "Spitzer RL", "Williams JB"],
      "year": 2001,
      "title": "The PHQ-9: validity of a brief depression severity measure",
      "journal": "Journal of General Internal Medicine",
      "doi": "10.1046/j.1525-1497.2001.016009606.x"
    },
    "original_source_url": "https://www.phqscreeners.com/",
    "license": "Public Domain",

    "prism_template": {
      "curated": true,
      "curated_by": "MRI-Lab Graz",
      "curated_date": "2024-01-01",
      "template_source": "curated_library"
    },

    "limesurvey_source": {
      "file": "sourcedata/structure/limesurvey/phq9.lss",
      "survey_id": 123456,
      "imported_date": "2024-01-15",
      "language": "de"
    }
  },

  "languages": ["de", "en"],
  "default_language": "de",

  "questions": [
    {
      "id": "phq9_q1",
      "variable_name": "phq9_q1",
      "text": {
        "de": "Wenig Interesse oder Freude an Ihren Tätigkeiten",
        "en": "Little interest or pleasure in doing things"
      },
      "type": "likert",
      "required": true,
      "levels": {
        "0": {"de": "Überhaupt nicht", "en": "Not at all"},
        "1": {"de": "An einzelnen Tagen", "en": "Several days"},
        "2": {"de": "An mehr als der Hälfte der Tage", "en": "More than half the days"},
        "3": {"de": "Beinahe jeden Tag", "en": "Nearly every day"}
      }
    }
  ],

  "scoring": {
    "total_score": {
      "formula": "sum(phq9_q1:phq9_q9)",
      "range": [0, 27],
      "interpretation": {
        "0-4": "Minimal depression",
        "5-9": "Mild depression",
        "10-14": "Moderate depression",
        "15-19": "Moderately severe depression",
        "20-27": "Severe depression"
      }
    }
  },

  "methods_boilerplate": "The PHQ-9 (Kroenke et al., 2001) was used to assess depressive symptoms. Participants rated 9 items on a 4-point scale (0-3). The total score (range 0-27) was calculated. The German version was administered."
}
```

### Methods Boilerplate

**Note:** Methods boilerplate is stored in **English only**. If questions are administered in other languages, this is mentioned in the boilerplate text (e.g., "The German version was administered."). The actual question text in other languages is stored in the question definitions.

### Provenance Source Types

| Type | Description | Example |
|------|-------------|---------|
| `published_instrument` | Validated questionnaire with citation | PHQ-9, GAD-7, BDI-II |
| `curated_template` | From PRISM curated library | MRI-Lab Graz templates |
| `limesurvey_import` | Imported from .lss/.lsa | Custom study survey |
| `custom` | User-created in PRISM | Study-specific questions |

---

## 4. Naming Conventions for Questionnaire Instances

### Recommended Naming in LimeSurvey

When using the same questionnaire multiple times:

```
Pattern: {questionnaire}_{instance}_q{number}

Examples:
- phq9_pre_q1, phq9_pre_q2, ...     (pre-intervention)
- phq9_post_q1, phq9_post_q2, ...   (post-intervention)
- phq9_fu1_q1, phq9_fu1_q2, ...     (follow-up 1)
- phq9_fu2_q1, phq9_fu2_q2, ...     (follow-up 2)

Recommended instance suffixes:
- _pre, _post          (intervention studies)
- _t1, _t2, _t3        (time points)
- _fu1, _fu2           (follow-ups)
- _a, _b               (repeated measures)
```

### Handling Non-Standard Naming

If naming doesn't follow convention, the system should:

1. **Detect patterns** - Find variable groups that look like questionnaires
2. **Show user** - "Found variables: phq9first_*, phq9second_* - same questionnaire?"
3. **Let user map** - User specifies which prefix maps to which instance
4. **Store mapping** - Save in import manifest for reproducibility

### Output File Naming

```
Instance → Task Name → Filename

null (default)  → phq9      → sub-001_ses-01_task-phq9_beh.tsv
"pre"           → phq9pre   → sub-001_ses-01_task-phq9pre_beh.tsv
"post"          → phq9post  → sub-001_ses-01_task-phq9post_beh.tsv
"followup1"     → phq9fu1   → sub-001_ses-01_task-phq9fu1_beh.tsv
```

---

## 5. Conversion Workflow with User Confirmation

### Step-by-Step Flow

```
┌────────────────────────────────────────────────────────────────┐
│ STEP 1: FILE UPLOAD                                            │
│                                                                │
│ [Upload .lsa/.csv/.xlsx file]                                  │
│                                                                │
│ File: study_export_2024-01.lsa                                 │
│ Type: LimeSurvey Archive (detected)                            │
│ Size: 2.4 MB                                                   │
│ Contains: 150 responses, 45 variables                          │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 2: SESSION SELECTION                          [Manual]    │
│                                                                │
│ Target Session: [ses-01 (Baseline)        ▼]                   │
│                                                                │
│ ○ Create new session: [____________]                           │
│                                                                │
│ ⚠️  Note: Session ses-01 already has 50 participants.          │
│     New data will be ADDED (duplicates will be flagged).       │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 3: QUESTIONNAIRE DETECTION                    [Assisted]  │
│                                                                │
│ Detected variable groups:                                      │
│                                                                │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Variables     │ Matches    │ Confidence │ Action        │   │
│ ├───────────────┼────────────┼────────────┼───────────────┤   │
│ │ phq9_q1-q9    │ PHQ-9      │ 95%        │ [✓ Confirm]   │   │
│ │ phq9post_q1-9 │ PHQ-9      │ 90%        │ [✓ Confirm]   │   │
│ │ gad7_q1-q7    │ GAD-7      │ 95%        │ [✓ Confirm]   │   │
│ │ custom_q1-q5  │ No match   │ -          │ [Map manually]│   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                │
│ [Expand] Show variable details                                 │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 4: INSTANCE CONFIGURATION                     [Manual]    │
│                                                                │
│ PHQ-9 appears twice. Configure instances:                      │
│                                                                │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Prefix       │ Instance   │ Task Name  │ Description    │   │
│ ├──────────────┼────────────┼────────────┼────────────────┤   │
│ │ phq9_        │ [none    ] │ phq9       │ [Baseline    ] │   │
│ │ phq9post_    │ [post    ] │ phq9post   │ [Post-interv.] │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                │
│ 💡 Tip: Use 'pre/post' for intervention studies,              │
│         't1/t2/t3' for repeated measures.                      │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 5: PARTICIPANT ID MAPPING                     [Assisted]  │
│                                                                │
│ ID Column: [participant_id ▼]                                  │
│                                                                │
│ Sample values: P001, P002, P003...                             │
│ Pattern detected: P{number}                                    │
│                                                                │
│ Transform to BIDS: P001 → sub-001                              │
│                   [✓ Confirm transformation]                   │
│                                                                │
│ ⚠️  Found 3 IDs that don't match pattern: TEST1, TEST2, ADMIN  │
│     [Skip these] [Map manually]                                │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 6: REVIEW & CONVERT                                       │
│                                                                │
│ Summary:                                                       │
│ • Source: study_export_2024-01.lsa                            │
│ • Session: ses-01                                              │
│ • Questionnaires: PHQ-9, PHQ-9 (post), GAD-7                  │
│ • Participants: 147 (3 skipped)                                │
│                                                                │
│ Output files to be created:                                    │
│ • sub-001/ses-01/survey/sub-001_ses-01_task-phq9_beh.tsv      │
│ • sub-001/ses-01/survey/sub-001_ses-01_task-phq9post_beh.tsv  │
│ • sub-001/ses-01/survey/sub-001_ses-01_task-gad7_beh.tsv      │
│ • ... (147 participants × 3 questionnaires)                   │
│                                                                │
│ [✓] Save import manifest to sourcedata/imports/                │
│ [✓] Archive source file to sourcedata/raw/                     │
│                                                                │
│ [Cancel]                              [Convert & Save]         │
└────────────────────────────────────────────────────────────────┘
```

### Merge Confirmation

When importing to a session with existing data:

```
┌────────────────────────────────────────────────────────────────┐
│ ⚠️  MERGE CONFIRMATION REQUIRED                                │
│                                                                │
│ Session ses-01 already contains data:                          │
│ • 50 existing participants                                     │
│ • Questionnaires: PHQ-9, GAD-7                                │
│                                                                │
│ New import will add:                                           │
│ • 100 new participants (147 total - 47 duplicates)            │
│                                                                │
│ Duplicate handling:                                            │
│ ○ Skip duplicates (keep existing)                              │
│ ○ Overwrite duplicates (use new data)                          │
│ ○ Flag for review (create _duplicate files)                    │
│                                                                │
│ [Cancel]                              [Confirm Merge]          │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. Template Lifecycle

### Creating Templates

```
                    ┌─────────────────────┐
                    │   PRISM Studio      │
                    │   Template Editor   │
                    └─────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ↓                  ↓                  ↓
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ Import from │    │ Create from │    │ Use curated │
    │ LimeSurvey  │    │ scratch     │    │ template    │
    │ (.lss/.lsa) │    │             │    │             │
    └─────────────┘    └─────────────┘    └─────────────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │  library/survey/    │
                    │  survey-xxx.json    │
                    └─────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ↓                  ↓                  ↓
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ Export to   │    │ Use for     │    │ Generate    │
    │ LimeSurvey  │    │ conversion  │    │ methods     │
    │ (.lss)      │    │             │    │ text        │
    └─────────────┘    └─────────────┘    └─────────────┘
```

### Template Sources and Trust Levels

| Source | Trust | Provenance | Use Case |
|--------|-------|------------|----------|
| **Published instrument** | High | DOI, citation | PHQ-9, BDI-II, standard measures |
| **Curated library** | High | MRI-Lab verified | Validated translations |
| **LimeSurvey import** | Medium | .lss file reference | Study-specific surveys |
| **Custom creation** | User | Created date, author | Novel questionnaires |

---

## 7. Implementation Priority

### Phase 1: Core Structure
- [ ] Implement sourcedata/ folder structure
- [ ] Create import manifest schema
- [ ] Basic import workflow with manual configuration

### Phase 2: Assisted Detection
- [ ] Variable pattern detection
- [ ] Template matching algorithm
- [ ] Confidence scoring

### Phase 3: Template Provenance
- [ ] Enhanced template schema with provenance
- [ ] Citation management
- [ ] Methods boilerplate generation

### Phase 4: Polish
- [ ] Merge conflict resolution
- [ ] Import history viewer
- [ ] Export to LimeSurvey (.lss generation)

---

## Open Questions

1. **Should we support importing the same file multiple times?** (e.g., re-import with different settings)
2. **How to handle templates that evolve over time?** (versioning)
3. **Should import manifests be human-editable?** (for corrections)
4. **Integration with LimeSurvey API** for direct sync?

---

*Document created: 2024-01-09*
*Last updated: 2024-01-09*
*Status: Draft for discussion*
