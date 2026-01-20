# PRISM Project Structure (YODA-Compliant)

This document describes the recommended folder structure for PRISM projects, following the [YODA principles](https://handbook.datalad.org/en/latest/basics/101-127-yoda.html).

## Overview

PRISM projects use a **YODA-compliant** structure that separates:
- **Data** (raw, processed, derivatives)
- **Code** (scripts, templates, recipes)
- **Outputs** (papers, figures)

This structure ensures reproducibility, version control friendliness, and compatibility with DataLad workflows.

## Complete Structure

```
my_study/                           # Project root
│
├── rawdata/                        # 📊 BIDS/PRISM raw data (READ-ONLY)
│   ├── dataset_description.json   # BIDS dataset metadata
│   ├── participants.tsv           # Participant roster
│   ├── participants.json          # Participant metadata
│   ├── .bidsignore                # BIDS validator ignore rules
│   ├── CHANGES                    # Dataset changelog
│   ├── sub-01/                    # Subject folders
│   │   ├── ses-01/                # Session folders (optional)
│   │   │   ├── survey/            # Survey data
│   │   │   │   ├── sub-01_ses-01_task-phq9_survey.tsv
│   │   │   │   └── sub-01_ses-01_task-phq9_survey.json
│   │   │   ├── biometrics/        # Biometric data
│   │   │   ├── physio/            # Physiological data
│   │   │   └── eyetracking/       # Eye-tracking data
│   │   └── ses-02/
│   └── sub-02/
│
├── code/                           # 💻 All code, templates, recipes (YODA)
│   ├── library/                   # Custom templates (project-specific)
│   │   ├── survey/                # Survey JSON templates
│   │   │   ├── survey-phq9-custom.json
│   │   │   └── survey-example.json
│   │   └── biometrics/            # Biometric JSON templates
│   │       └── biometrics-example.json
│   ├── recipes/                   # Custom scoring recipes (project-specific)
│   │   ├── survey/                # Survey scoring recipes
│   │   │   ├── phq9.json
│   │   │   └── gad7.json
│   │   └── biometrics/            # Biometric processing recipes
│   ├── scripts/                   # Analysis scripts
│   │   ├── import_limesurvey.py
│   │   ├── process_ecg.py
│   │   └── run_analysis.R
│   └── README                     # Code folder documentation
│
├── derivatives/                    # 📈 Processed/derived data outputs
│   ├── survey/                    # Survey scores (from recipes)
│   │   ├── dataset_description.json
│   │   ├── sub-01/
│   │   │   └── ses-01/
│   │   │       └── survey/
│   │   │           └── sub-01_ses-01_task-phq9_desc-scores_beh.tsv
│   │   └── survey_scores.tsv      # Flat format (all subjects)
│   ├── biometrics/                # Biometric derivatives
│   └── qc/                        # Quality control reports
│       ├── validation_report.html
│       └── validator_output.json
│
├── sourcedata/                     # 🗃️ Original/unconverted data
│   ├── limesurvey_exports/        # Raw LimeSurvey files (.lss)
│   ├── excel_surveys/             # Original Excel/CSV files
│   ├── ecg_raw/                   # Raw ECG data
│   └── data_dictionary.tsv        # Variable definitions
│
├── analysis/                       # 📊 Statistical analysis
│   ├── scripts/                   # R, Python, SPSS scripts
│   ├── notebooks/                 # Jupyter notebooks
│   └── results/                   # Statistical outputs
│       ├── tables/
│       └── figures/
│
├── paper/                          # 📝 Manuscripts and publications
│   ├── manuscript.md              # Manuscript source
│   ├── figures/                   # Publication-ready figures
│   ├── supplements/               # Supplementary materials
│   └── submission/                # Journal submission files
│
├── stimuli/                        # 🎬 Stimulus files (optional)
│   ├── images/
│   ├── videos/
│   └── audio/
│
├── .prismrc.json                   # ⚙️ Project configuration
├── project.json                    # Project metadata
├── contributors.json               # Contributor information
├── CITATION.cff                    # Citation information
└── README.md                       # Project overview

```

## Folder Descriptions

### Data Folders

#### `rawdata/` (BIDS Root)
- **Purpose**: Raw, untouched BIDS/PRISM data
- **Access**: Read-only after collection
- **Contents**: Subject folders, metadata, participant info
- **Validation**: Use PRISM validator to check compliance

#### `derivatives/`
- **Purpose**: Processed/scored data outputs
- **Generated by**: Recipe processing, scoring scripts
- **Structure**: Mirrors `rawdata/` structure
- **Examples**: Survey scores, HRV metrics, preprocessed signals

#### `sourcedata/`
- **Purpose**: Original data before BIDS conversion
- **Contents**: Raw exports (LimeSurvey, Excel, device outputs)
- **Note**: Keep original files for reproducibility

### Code Folder (YODA-Compliant)

#### `code/library/` - Templates
- **Purpose**: Project-specific templates that customize or extend global templates
- **Structure**: `{modality}/` subfolders (survey, biometrics, etc.)
- **Priority**: Overrides global templates with same filename
- **Edit via**: Template Editor in PRISM Studio

**Example Use Cases:**
- Customizing a global survey template (e.g., paper-pencil vs. online)
- Adding study-specific metadata fields
- Creating new questionnaires not in global library

**File Naming:**
- `survey-{name}.json` for surveys
- `biometrics-{name}.json` for biometrics

#### `code/recipes/` - Scoring/Processing
- **Purpose**: Project-specific scoring recipes and transformation logic
- **Structure**: `{modality}/` subfolders (survey, biometrics, etc.)
- **Priority**: Overrides global recipes with same filename
- **Format**: JSON with scoring formulas, subscales, reverse coding

**Example Use Cases:**
- Custom scoring rules for modified questionnaires
- Study-specific cutoff values
- Combined scores from multiple instruments

**File Naming:**
- `{recipe-name}.json` matching the survey/biometric name

#### `code/scripts/`
- **Purpose**: Custom analysis and processing scripts
- **Languages**: Python, R, MATLAB, bash, etc.
- **Examples**: Data import scripts, preprocessing pipelines

### Analysis & Output Folders

#### `analysis/`
- **Purpose**: Statistical analysis code and results
- **Typical contents**: R/Python scripts, Jupyter notebooks, SPSS syntax
- **Outputs**: Tables, figures, statistical reports

#### `paper/`
- **Purpose**: Manuscripts, figures, publication materials
- **Format**: Markdown, LaTeX, Word, etc.
- **Integration**: Can reference `analysis/results/` for automated figure inclusion

#### `stimuli/` (Optional)
- **Purpose**: Stimulus files used in experiments
- **Examples**: Images, videos, audio files, experimental paradigms

## YODA Principles in PRISM

PRISM's structure follows these YODA principles:

1. **Separation of Concerns**:
   - Data (`rawdata/`, `derivatives/`) is separate from code (`code/`)
   - Outputs (`analysis/results/`, `paper/`) are separate from inputs

2. **Reproducibility**:
   - All code needed to reproduce results lives in `code/`
   - Templates and recipes are versioned alongside analysis scripts

3. **DataLad Compatibility**:
   - Structure is compatible with DataLad datasets
   - `rawdata/` can be a DataLad subdataset
   - `code/` can track code separately from data

4. **Self-Contained**:
   - Each project contains all necessary definitions
   - No external dependencies (beyond global library references)

## Template & Recipe Priority System

PRISM uses a **two-tier system** for templates and recipes:

### Global (Read-Only)
Located in `official/library/` and `official/recipes/` (or configured global path):
- ✅ Shared, validated, standardized definitions
- ✅ Updated centrally (e.g., via git pull)
- ✅ Available to all projects
- ❌ Cannot be edited directly

### Project-Local (Writable)
Located in `{project}/code/library/` and `{project}/code/recipes/`:
- ✅ Project-specific customizations
- ✅ Overrides global definitions (same filename)
- ✅ New definitions not in global library
- ✅ Fully editable

### Priority Resolution

When PRISM looks for `survey-phq9.json`, it checks:

1. **`{project}/code/library/survey/survey-phq9.json`** ← Project-local (highest priority)
2. **`official/library/survey/survey-phq9.json`** ← Global (fallback)

Same for recipes:

1. **`{project}/code/recipes/survey/phq9.json`** ← Project-local (highest priority)
2. **`official/recipes/survey/phq9.json`** ← Global (fallback)

This allows you to:
- Use global templates as-is (no local copy needed)
- Customize when needed (create local copy with same name)
- Add new definitions (create local file with new name)

## Migration from Legacy Structure

If you have an older PRISM project with:
- `library/` at root level → Move to `code/library/`
- `recipe/` at root level → Move to `code/recipes/`

**Migration Steps:**

```bash
# From your project root
cd my_study/

# Move library
mv library/ code/library/

# Move recipes
mv recipe/ code/recipes/

# Verify structure
ls code/library/survey/
ls code/recipes/survey/
```

PRISM maintains backwards compatibility and will check legacy locations if new ones don't exist.

## Validation

To validate your project structure:

**CLI:**
```bash
python prism.py /path/to/my_study
```

**Web UI:**
1. Open PRISM Studio
2. Go to Projects → Select project
3. Click "Validate Structure"

The validator checks for:
- Required BIDS files in `rawdata/`
- Proper folder hierarchy
- PRISM-specific metadata
- Code folder organization (recommendation, not enforced)

## Best Practices

### ✅ DO:
- **Keep `rawdata/` untouched** after initial collection
- **Version control `code/`** (git repository)
- **Document changes** in `rawdata/CHANGES` and project README
- **Use relative paths** in scripts (assume project root as base)
- **Backup `sourcedata/`** before converting to BIDS

### ❌ DON'T:
- **Edit `rawdata/` directly** after validation passes
- **Mix data and code** in the same folder
- **Hard-code absolute paths** in scripts
- **Delete `sourcedata/`** after conversion (keep originals!)
- **Put large files in `code/`** (use `rawdata/` or `stimuli/`)

## Examples

### Example 1: Simple Survey Study

```
survey_study/
├── rawdata/
│   ├── dataset_description.json
│   ├── participants.tsv
│   └── sub-*/ses-*/survey/
├── code/
│   ├── library/survey/
│   │   └── survey-phq9-german.json    # Customized version
│   └── recipes/survey/
│       └── phq9.json                   # Custom cutoffs
├── derivatives/survey/
│   └── survey_scores.tsv
└── analysis/
    └── scripts/correlation_analysis.R
```

### Example 2: Multi-Modal Study

```
multimodal_study/
├── rawdata/
│   └── sub-*/ses-*/
│       ├── survey/
│       ├── biometrics/
│       ├── physio/
│       └── eyetracking/
├── code/
│   ├── library/
│   │   ├── survey/
│   │   └── biometrics/
│   ├── recipes/
│   │   ├── survey/
│   │   └── biometrics/
│   └── scripts/
│       ├── import_all.py
│       ├── preprocess_ecg.py
│       └── sync_eyetracking.py
├── derivatives/
│   ├── survey/
│   ├── biometrics/
│   └── qc/
└── stimuli/
    └── video_clips/
```

## Related Documentation

- [YODA Principles](https://handbook.datalad.org/en/latest/basics/101-127-yoda.html)
- [BIDS Specification](https://bids-specification.readthedocs.io/)
- [Template Customization](TEMPLATE_CUSTOMIZATION.md)
- [Global Library Configuration](GLOBAL_LIBRARY_CONFIG.md)
- [Recipe System](RECIPES.md)

## Summary

PRISM's YODA-compliant structure ensures:
- ✅ **Clear separation** of data, code, and outputs
- ✅ **Version control** friendly (small code files, large data separate)
- ✅ **Reproducible** workflows (all definitions in `code/`)
- ✅ **Shareable** projects (standard structure everyone understands)
- ✅ **DataLad compatible** (can use subdatasets for large data)

The key principle: **Everything needed to reproduce your analysis lives in `code/`, and all raw data lives in `rawdata/`**.
