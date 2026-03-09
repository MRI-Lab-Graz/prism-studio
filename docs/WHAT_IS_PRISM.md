# What is PRISM?

PRISM (Psychological Research Information System Model) is a data-structure and metadata model for psychological experiment datasets. It extends the [BIDS standard](https://bids.neuroimaging.io/) to support modalities common in psychological research-like surveys, biometrics, eyetracking, and environment-while ensuring your data remains fully compatible with existing BIDS tools.

PRISM Studio is the software that implements PRISM workflows such as conversion, validation runs, scoring execution, and export.

## PRISM is an Add-On, Not a Replacement

```{important}
PRISM does not replace BIDS—it enhances it. Your PRISM-validated datasets will still work with fMRIPrep, MRIQC, and all other BIDS apps.
```

| Aspect | BIDS | PRISM |
|--------|------|-------|
| **Focus** | Neuroimaging (MRI, EEG, MEG) | Psychological experiments |
| **Surveys** | Limited support | Full support with item descriptions |
| **Biometrics** | Not clearly standardized | Sports/performance tests (e.g., VO2max, Y-Balance, CMJ) with rich metadata |
| **Physio** | Basic support | Primarily EDF+/EDF signal workflows, plus TSV-based recordings with metadata |
| **Eyetracking** | Emerging support | Complete schema validation |
| **Environment** | Not standardized in practice | Structured environmental context sidecars |
| **Scoring execution** | Not included | Implemented in PRISM Studio (recipes/derivatives tools) |
| **Export workflows** | Raw data focus | Implemented in PRISM Studio (SPSS/CSV/integration exports) |

### How PRISM Stays BIDS-Compatible

PRISM uses a `.bidsignore` file to tell BIDS validators to skip PRISM-specific files. This means:

- ✅ Standard BIDS apps (fMRIPrep, MRIQC) work normally
- ✅ Your MRI data validates against the BIDS standard
- ✅ PRISM-model files and PRISM Studio outputs are organized alongside your data
- ✅ One dataset, one folder structure, maximum compatibility

## Key Benefits

### 1. 🔍 Validation

Catch errors before they become problems:

- **Structured error codes** (PRISM001–PRISM999) with clear explanations
- **Auto-fix** for common issues
- **Severity levels**: Errors, warnings, and suggestions
- **BIDS validation** can run alongside PRISM validation

### 2. 📝 Self-Documenting Data

Every data file has a sidecar JSON with complete metadata:

```json
{
  "SurveyName": "Best Inventory Ever",
  "Items": [
    {
      "ItemID": "BIE01",
      "Question": {
        "en": "Sadness",
        "de": "Traurigkeit"
      },
      "ResponseOptions": {
        "0": "I do not feel sad",
        "1": "I feel sad much of the time",
        "2": "I am sad all the time",
        "3": "I am so sad I can't stand it"
      }
    }
  ]
}
```

This makes your data:
- **Understandable** without external documentation
- **Reusable** by other researchers
- **FAIR-compliant** (Findable, Accessible, Interoperable, Reusable)

### 3. 📊 Questionnaire Scoring in PRISM Studio

Scoring is a **PRISM Studio software feature**, not part of the PRISM model itself.

Calculate scores automatically with **recipes** in PRISM Studio:

```json
{
  "RecipeName": "BIE Total Score",
  "Scoring": {
    "DEMO_total": {
      "operation": "sum",
      "items": ["IE01", "BIE02", "BIE03", "..."]
    }
  }
}
```

### 4. 📤 SPSS-Ready Export in PRISM Studio

PRISM Studio can export scored data directly to SPSS (.save) with:
- Variable labels
- Value labels (e.g., 1 = "Male", 2 = "Female")
- Proper data types

### 5. 🌐 Web Interface

PRISM Studio provides a user-friendly interface for:
- Creating and managing projects
- Converting Excel/CSV/SPSS data
- Validating datasets
- Running scoring recipes
- Browsing the survey library

### Model vs Software Boundary

- **PRISM** defines structure, naming, and metadata expectations.
- **PRISM Studio** provides operational tooling like conversion, validation runs, scoring execution, and exports.

## Supported Modalities

| Modality | File Extension | Description |
|----------|---------------|-------------|
| **survey** | `.tsv` + `.json` | Questionnaires, assessments |
| **biometrics** | `.tsv` + `.json` | Sports/performance tests (e.g., VO2max, Y-Balance, CMJ, sit-and-reach) |
| **eyetracking** | `.tsv` + `.json` | Gaze data, fixations, saccades |
| **physiological** | `.edf`/`.edf+` or `.tsv`/`.tsv.gz` + `.json` | Continuous physiological signals (ECG, EMG, respiration, EDA) |
| **environment** | `.tsv` + `.json` | Environmental/contextual derivatives and sidecars |
| **events** | `.tsv` + `.json` | Stimulus presentation logs |
| **anat/func/dwi/fmap** | Standard BIDS | MRI data (validated by BIDS) |
| **eeg** | Standard BIDS-EEG | EEG data (validated by BIDS) |

## Project Structure (YODA Layout)

PRISM encourages the [YODA principles](https://handbook.datalad.org/en/latest/basics/101-127-yoda.html) for reproducible research:

```
my_study/
├── dataset_description.json
├── participants.tsv
├── participants.json
├── sub-001/
│   └── survey/
│       ├── sub-001_task-demo_survey.tsv
│       └── sub-001_task-demo_survey.json
├── code/                       # Analysis scripts
├── analysis/                   # Results and derivatives
└── project.json               # Project metadata
```

## Next Steps

- **[Installation](INSTALLATION.md)** – Get PRISM running in 5 minutes
- **[Quick Start](QUICK_START.md)** – Your first PRISM project
- **[Workshop](WORKSHOP.md)** – Hands-on exercises with example data
