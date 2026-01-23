# What is PRISM?

PRISM (**P**sychological **R**esearch **I**nformation **S**tructure for **M**etadata) is a validation and metadata framework for psychological experiment datasets. It extends the [BIDS standard](https://bids.neuroimaging.io/) to support modalities common in psychological research—like surveys, biometrics, and eyetracking—while ensuring your data remains fully compatible with existing BIDS tools.

## PRISM is an Add-On, Not a Replacement

```{important}
PRISM does not replace BIDS—it enhances it. Your PRISM-validated datasets will still work with fMRIPrep, MRIQC, and all other BIDS apps.
```

| Aspect | BIDS | PRISM |
|--------|------|-------|
| **Focus** | Neuroimaging (MRI, EEG, MEG) | Psychological experiments |
| **Surveys** | Limited support | Full support with item descriptions |
| **Biometrics** | Basic physio | ECG, EMG, respiration with metadata |
| **Eyetracking** | Emerging support | Complete schema validation |
| **Scoring** | Not included | Recipe system for questionnaire scoring |
| **Export** | Raw data focus | SPSS export with value labels |

### How PRISM Stays BIDS-Compatible

PRISM uses a `.bidsignore` file to tell BIDS validators to skip PRISM-specific files. This means:

- ✅ Standard BIDS apps (fMRIPrep, MRIQC) work normally
- ✅ Your MRI data validates against the BIDS standard
- ✅ PRISM-specific files (surveys, recipes) are organized alongside your data
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
  "SurveyName": "Beck Depression Inventory",
  "Items": [
    {
      "ItemID": "BDI01",
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

### 3. 📊 Questionnaire Scoring

Calculate scores automatically with **recipes**:

```json
{
  "RecipeName": "BDI Total Score",
  "Scoring": {
    "BDI_total": {
      "operation": "sum",
      "items": ["BDI01", "BDI02", "BDI03", "..."]
    }
  }
}
```

### 4. 📤 SPSS-Ready Export

Export your scored data directly to SPSS (.sav) with:
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

## Supported Modalities

| Modality | File Extension | Description |
|----------|---------------|-------------|
| **survey** | `.tsv` + `.json` | Questionnaires, assessments |
| **biometrics** | `.tsv` + `.json` | ECG, EMG, respiration, skin conductance |
| **eyetracking** | `.tsv` + `.json` | Gaze data, fixations, saccades |
| **physiological** | `.tsv.gz` + `.json` | Continuous physio recordings |
| **events** | `.tsv` + `.json` | Stimulus presentation logs |
| **anat/func/dwi/fmap** | Standard BIDS | MRI data (validated by BIDS) |
| **eeg** | Standard BIDS-EEG | EEG data (validated by BIDS) |

## Project Structure (YODA Layout)

PRISM encourages the [YODA principles](https://handbook.datalad.org/en/latest/basics/101-127-yoda.html) for reproducible research:

```
my_study/
├── rawdata/                    # ← PRISM validates here
│   ├── dataset_description.json
│   ├── participants.tsv
│   ├── participants.json
│   └── sub-001/
│       └── survey/
│           ├── sub-001_task-bdi_survey.tsv
│           └── sub-001_task-bdi_survey.json
├── code/                       # Analysis scripts
├── analysis/                   # Results and derivatives
└── project.json               # Project metadata
```

## Next Steps

- **[Installation](INSTALLATION.md)** – Get PRISM running in 5 minutes
- **[Quick Start](QUICK_START.md)** – Your first PRISM project
- **[Workshop](WORKSHOP.md)** – Hands-on exercises with example data
