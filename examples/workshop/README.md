# PRISM Workshop Demo Data

This folder contains materials for the PRISM hands-on workshop focused on **wellbeing survey analysis** using the WHO-5 Well-Being Index.

## 📚 Workshop Documentation

- **[WORKSHOP_HANDOUT_WELLBEING.md](WORKSHOP_HANDOUT_WELLBEING.md)** - Complete step-by-step guide for participants
- **[PREPARATION.md](PREPARATION.md)** - Setup checklist for instructors
- **[STRUCTURE.md](STRUCTURE.md)** - Technical details about folder organization

## 🎯 Exercises Overview (Basics Track)

### Exercise 0: Project Setup (YODA)
- **Goal:** Create organized research project following YODA principles
- **Duration:** 15 minutes
- **Folder:** `exercise_0_project_setup/`
- **Key Concept:** Separation of raw data, analysis, and results

### Exercise 1: Data Conversion
- **Goal:** Convert `wellbeing.xlsx` to PRISM format
- **Duration:** 30 minutes  
- **Materials:** `exercise_1_raw_data/raw_data/wellbeing.xlsx` & `wellbeing.tsv`
- **Output:** BIDS-structured dataset with participants and survey files

### Exercise 2: Metadata & Validation
- **Goal:** Validate converted survey data and fix missing metadata
- **Duration:** 25 minutes
- **Folder:** `exercise_2_hunting_errors/`
- **Key Concept:** Use validator feedback to complete sidecar metadata

### Exercise 3: Scoring & Export
- **Goal:** Calculate wellbeing scores and export to SPSS
- **Duration:** 20 minutes
- **Recipe:** `exercise_3_using_recipes/recipe-wellbeing.json`
- **Output:** SPSS file with calculated total scores

## ➕ Optional Extensions

### Participant Mapping (Advanced)
- **Goal:** Transform demographic data with custom encodings to standardized PRISM format
- **Duration:** 30-45 minutes
- **Folder:** `exercise_5_participant_mapping/`
- **Key Concept:** Using `participants_mapping.json` to auto-transform demographic variables

### Templates
- **Goal:** Create reusable survey template metadata
- **Duration:** 20 minutes
- **Folder:** `exercise_4_templates/`
- **Template Example:** `exercise_4_templates/survey-wellbeing.json`

## 📁 Quick Reference

### Raw Data
- **Location:** `exercise_1_raw_data/raw_data/`
- **Files:** 
  - `wellbeing.xlsx` - Excel format (recommended for workshop)
  - `wellbeing.tsv` - Tab-delimited alternative
  - `fitness_data.tsv` - Optional additional exercise

### Survey Information
- **Instrument:** WHO-5 Well-Being Index (5 items)
- **Columns:** WB01, WB02, WB03, WB04, WB05
- **Scale:** 0-5 (0 = At no time, 5 = All of the time)
- **Score Range:** 5-35 (sum of all items)

### Templates & Recipes
- **Survey Template:** `exercise_4_templates/survey-wellbeing.json`
- **Recipe:** `exercise_3_using_recipes/recipe-wellbeing.json`
- **Official Library:** `../../official/library/survey/survey-who5.json`
- **Official Recipe:** `../../official/recipe/survey/recipe-who5.json`

## 🚀 Getting Started

1. **Read:** [WORKSHOP_HANDOUT_WELLBEING.md](WORKSHOP_HANDOUT_WELLBEING.md)
2. **Launch:** PRISM Studio (`source .venv/bin/activate && ./prism-studio.py` on macOS/Linux, or `.\.venv\Scripts\Activate.ps1` then `python prism-studio.py` on Windows)
3. **Start:** Exercise 0 - Create your project
4. **Follow:** Step-by-step instructions in each exercise folder

> Note: This branch uses a newer PRISM Studio UI. Some labels may appear as `Recipes` vs `Recipes & Scoring` and routes follow `/projects`, `/converter`, `/validate`, `/recipes`, and `/template-editor`.

## 💡 Tips for Instructors

- Allow 90-120 minutes total for all exercises
- Emphasize YODA principles in Exercise 0
- Show the raw data file first so participants understand what they're converting
- Have participants validate after Exercise 1 to see what's missing
- Use Exercise 2 to teach importance of metadata
- Demonstrate SPSS export in Exercise 3 with value labels

## 📖 Additional Resources

- **CLI Reference:** `../../docs/CLI_REFERENCE.md`
- **Web Interface Guide:** `../../docs/WEB_INTERFACE.md`
- **Survey Library:** `../../docs/SURVEY_LIBRARY.md`
- **Recipe Creation:** `../../docs/RECIPES.md`
