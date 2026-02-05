# Workshop Preparation Guide

This document describes the **preparation steps** that need to be completed **before** the workshop. These are not part of the participant exercises.

## Overview

The workshop uses the **WHO-5 Well-Being Index** as the example survey. Participants will:
1. Set up a new PRISM project using YODA principles (Exercise 0)
2. Convert raw wellbeing data from Excel to PRISM format (Exercise 1)
3. Validate and fix metadata errors (Exercise 2)
4. Apply recipes to calculate scores and export to SPSS (Exercise 3)

## Pre-Workshop Setup (Instructor)

### 1. Official Library Entry (Already Done ✓)

The WHO-5 survey library entry already exists at:
```
official/library/survey/survey-who5.json
```

This file contains:
- Complete survey metadata (name, authors, citation)
- Item-level descriptions and response scales
- Scoring information

**No action needed** - this is already in the repository.

### 2. Official Recipe (Already Done ✓)

The WHO-5 scoring recipe already exists at:
```
official/recipe/survey/recipe-who5.json
```

This recipe defines:
- Total score calculation (sum of 5 items)
- Score range (5-35)
- Scoring guidelines

**No action needed** - this is already in the repository.

### 3. Raw Data File (Already Exists ✓)

Located at:
```
examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx
examples/workshop/exercise_1_raw_data/raw_data/wellbeing.tsv
```

These files contain:
- Column: `participant_id` (e.g., DEMO001, DEMO002, ...)
- Column: `session` (e.g., baseline)
- Demographics: `age`, `sex`, `education`, `handedness`
- Survey columns: `WB01`, `WB02`, `WB03`, `WB04`, `WB05`
- Column: `completion_date`
- Data: Sample participants with realistic responses (0-5 scale)

**Note:** The column names `WB01`-`WB05` will need to be mapped to WHO-5 item names (`WHO501`-`WHO505`) during conversion, or participants can use them as-is and update the recipe accordingly.

**Participants will convert this file during Exercise 1.**

## What Participants Will Do

### Exercise 0: Project Setup with YODA
- Learn about YODA principles (Yet anOther Data Analysis)
- Create a new PRISM project with proper folder structure
- Understand the separation of raw data, analysis, and results

**Files:** `examples/workshop/exercise_0_project_setup/INSTRUCTIONS.md`

### Exercise 1: Convert Raw Data
- Upload `wellbeing.xlsx` (or `wellbeing.tsv`)
- Use PRISM Studio's converter to transform it to BIDS/PRISM format
- Map columns: `participant_id` → subject ID, `session` → session ID
- Map survey items: `WB01`-`WB05` → either keep as-is or rename to `WHO501`-`WHO505`
- Generate proper file structure:
  ```
  sub-DEMO001/
    ses-baseline/
      survey/
        sub-DEMO001_ses-baseline_task-wellbeing_survey.tsv
        sub-DEMO001_ses-baseline_task-wellbeing_survey.json
  ```

**Files:** `examples/workshop/exercise_1_raw_data/INSTRUCTIONS.md`

### Exercise 2: Validate & Fix Metadata
- Run validator on the converted dataset
- Identify missing metadata fields
- Use the Template Editor to add proper metadata
- Copy from official library: `survey-who5.json`
- Validate again to ensure all errors are fixed

**Files:** `examples/workshop/exercise_2_hunting_errors/INSTRUCTIONS.md`

### Exercise 3: Apply Recipes & Export
- Copy recipe from official library: `recipe-who5.json`
- Run recipe to calculate total wellbeing scores
- Export results to SPSS (.save) format with proper value labels
- Verify in Excel/SPSS that scores are correct

**Files:** `examples/workshop/exercise_3_using_recipes/INSTRUCTIONS.md`

## Workshop Materials Checklist

- [x] WHO-5 survey library entry (official/library/survey/survey-who5.json)
- [x] WHO-5 recipe (official/recipe/survey/recipe-who5.json)
- [x] Raw data files (examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx & .tsv)
- [ ] Update recipe to match column names (WB01-WB05 instead of WHO501-WHO505) OR rename columns in data
- [ ] Exercise 0 instructions (YODA project setup)
- [ ] Exercise 1 instructions (convert Excel to PRISM)
- [ ] Exercise 2 instructions (validate and fix metadata)
- [ ] Exercise 3 instructions (apply recipe and export)
- [ ] Updated WORKSHOP_HANDOUT.md
- [ ] Updated WORKSHOP_PLAN.md

## Testing the Workshop

Before running the workshop, test the complete flow:

1. **Start fresh:**
   ```powershell
   python prism-studio.py
   ```

2. **Exercise 0:** Create new project via Projects page
   
3. **Exercise 1:** Convert wellbeing.xlsx using the converter

4. **Exercise 2:** 
   - Validate the dataset
   - Add metadata from survey-who5.json
   - Re-validate to confirm fixes

5. **Exercise 3:**
   - Copy recipe-who5.json to project recipes folder
   - Run recipe
   - Export to SPSS
   - Open in Excel/SPSS to verify

**Total estimated time:** 90-120 minutes

## Notes

- The WHO-5 is a short, well-validated scale - perfect for workshop timing
- All items use the same response scale - simplifies the exercise
- Official library entries are "read-only" - participants copy them to their project
- Recipes are reusable - can be applied to multiple datasets
