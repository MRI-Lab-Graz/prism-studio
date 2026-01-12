# PRISM Workshop Demo Data

This folder contains materials for the PRISM hands-on workshop. The workshop teaches participants how to use the PRISM GUI to convert raw data, create metadata, and export analysis-ready outputs.

## Contents

### 1. `exercise_1_raw_to_bids/`
**Purpose:** Starting point for Exercise 1 (Raw Data Conversion)

- **Main File:** `wellbeing.tsv` - Wellness survey data.
- **Bonus File:** `fitness_data.tsv` - Biometric data.

---

### 2. `exercise_2_json_metadata/`
**Purpose:** Exercise 2 (Validation & Troubleshooting)

- **Materials:** `bad_examples/` folder with intentionally malformed data.

---

### 3. `exercise_3_recipes_export/`
**Purpose:** Exercise 3 (Recipes & SPSS Export)

- **Recipes:** `wellbeing.json`, `fitness.json`

**Current Use:** Not used in new workshop plan

**Status:** ⚠️ Can be kept for reference but not part of main workshop flow

**Notes:**
- Old workshop focused on fixing an already-structured dataset
- New workshop focuses on creating a dataset from scratch
- Can be used as a bonus "troubleshooting" exercise if time permits

---

### 4. `valid_dataset/`
**Purpose:** Reference implementation - completed example for participants to compare

### 4. `valid_dataset/`
**Purpose:** Reference implementation - completed example for participants to compare

**Status:** ⚠️ Needs to be created/updated

**Should Contain:**
A fully completed PRISM dataset that participants can reference, including wellbeing and fitness data.

---

## Required Supporting Files

### 1. Library Template: `library/survey/wellbeing.json`
**Purpose:** Reusable template for Wellbeing metadata

**Status:** ✓ Provided in library

### 2. Scoring Recipes: `demo/workshop/recipes/`
**Purpose:** Automated scoring logic for Exercise 3.
