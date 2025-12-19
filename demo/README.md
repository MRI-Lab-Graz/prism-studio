# Prism-Validator Demo Data

This folder contains **synthetic demo data** for testing and learning Prism-Validator workflows. All data is fictional and safe to share.

## Folder Structure

```
demo/
├── README.md                           # This file
├── templates/                          # JSON sidecar templates (multilingual)
│   ├── survey/
│   │   └── survey-wellbeing.json       # Well-being questionnaire (DE/EN in one file)
│   └── biometrics/
│       └── biometrics-fitness.json     # Fitness assessment (DE/EN in one file)
├── derivatives/                        # Scoring recipes for computed measures
│   ├── README.md                       # Documentation for derivative recipes
│   ├── surveys/
│   │   └── wellbeing.json              # Subscales, reverse coding for wellbeing
│   └── biometrics/
│       └── fitness.json                # Composite scores for fitness
├── raw_data/                           # Dummy data files (TSV format)
│   ├── survey_wellbeing_data.tsv       # Survey responses
│   └── biometrics_fitness_data.tsv     # Fitness measurements
├── flat_structure_example/             # Example of UNORGANIZED data
│   ├── README.md                       # Why this is problematic
│   └── *.csv                           # Messy, inconsistently named files
└── prism_structure_example/            # Example of ORGANIZED PRISM data
    ├── dataset_description.json
    ├── participants.tsv
    ├── participants.json
    ├── sub-001/
    │   ├── eyetrack/
    │   └── physio/
    └── sub-002/
        ├── eyetrack/
        └── physio/
```

## Key Features

### Multilingual Templates (I18n)

Templates use the PRISM i18n format with **both languages in a single file**:

```json
{
  "Study": {
    "OriginalName": {
      "de": "Wohlbefindens-Kurzskala",
      "en": "Well-Being Short Scale"
    }
  },
  "I18n": {
    "Languages": ["de", "en"],
    "DefaultLanguage": "en"
  },
  "WB01": {
    "Description": {
      "de": "Wie zufrieden sind Sie mit Ihrem Leben?",
      "en": "How satisfied are you with your life?"
    },
    "Levels": {
      "1": {"de": "Überhaupt nicht", "en": "Not at all"},
      "5": {"de": "Äußerst", "en": "Extremely"}
    }
  }
}
```

### Derivative Recipes

The `derivatives/` folder contains JSON recipes for computing scores:

- **Survey (wellbeing.json)**:
  - Scale inversion (WB03 stress item is reverse-coded)
  - Subscales: Total, Positive Affect, Life Satisfaction
  
- **Biometrics (fitness.json)**:
  - Derived measures (grip strength average, HR recovery)
  - Composite scores (cardio, strength, flexibility, total fitness)

## How to Use

### Testing Validation
```bash
# Activate virtual environment
source .venv/bin/activate

# Validate the well-organized PRISM dataset
python prism-validator.py demo/prism_structure_example/

# Try to validate the flat structure (will show errors!)
python prism-validator.py demo/flat_structure_example/
```

### Using Templates
```bash
# Compile i18n template to German
python prism_tools.py library-compile demo/templates/survey/survey-wellbeing.json --lang de

# Compile i18n template to English
python prism_tools.py library-compile demo/templates/survey/survey-wellbeing.json --lang en
```

### Generating Derivatives
```bash
# Generate survey scores from PRISM data
python prism_tools.py derivatives-surveys /path/to/dataset \
    --recipe demo/derivatives/surveys/wellbeing.json
```

### Web Interface
1. Start the web interface: `python prism-validator-web.py`
2. Upload the `prism_structure_example/` folder to see successful validation
3. Try uploading `flat_structure_example/` to see common issues

## Contents

### 1. Templates (`templates/`)
- Ready-to-use JSON sidecars for surveys and biometrics
- **Multilingual**: German and English in the same file
- Copy and modify for your own instruments

### 2. Derivatives (`derivatives/`)
- Scoring recipes for computing subscales and composite scores
- Demonstrates scale inversion and missing data handling
- Can be used with `prism_tools.py derivatives-surveys`

### 3. Raw Data (`raw_data/`)
- Example TSV files showing how source data typically looks
- Use these to practice data conversion workflows

### 4. Flat Structure Example (`flat_structure_example/`)
- Shows how data often arrives: chaotic, inconsistent naming
- Demonstrates WHY standardized structure is important
- Compare with the organized version to see the benefits

### 5. PRISM Structure Example (`prism_structure_example/`)
- Shows proper PRISM/BIDS-compatible organization
- Includes JSON sidecars and correctly named files
- Validates successfully with Prism-Validator

## Note

All data in this demo is **completely synthetic** and contains no real participant information.
Feel free to share, modify, or use for testing purposes.
