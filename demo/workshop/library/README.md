# Workshop Library Templates

This folder contains templates and recipes needed for the workshop exercises. All files are self-contained within the workshop folder structure.

## Structure

```
library/
├── survey/              ← Survey templates (metadata)
│   └── survey-phq9.json
└── biometrics/          ← Biometric templates (future)
```

This mirrors the main PRISM library structure at `library/survey/` and `library/biometrics/`.


## Contents

### Survey Templates
- **`survey/survey-phq9.json`** - Complete PHQ-9 metadata template
  - Used in **Exercise 2** as a reference
  - Contains all item descriptions and value labels
  - Can be copied/adapted for your own data
  - Follows PRISM naming convention: `survey-<instrument>.json`

### Survey Recipes
Recipes are **not** stored in `library/`. They belong in the workshop `recipes/surveys/` folder:
- **`demo/workshop/recipes/surveys/phq9.json`** - PHQ-9 scoring recipe
  - Used in **Exercise 3** for automated scoring
  - Defines how to calculate the total score
  - Includes interpretation categories
  - PRISM will find it when you select "phq9" from the recipes dropdown in the GUI

## Usage

1. Open `survey/survey-phq9.json` as a reference
2. Copy relevant sections (descriptions, levels)
3. Paste into your own files
4. Modify as needed

**Tip:** Use a diff tool to compare your work with the template.

### In Exercise 3 (Recipes & Export):
The recipe file is already in the correct location:
- **`demo/workshop/recipes/surveys/phq9.json`**

## File Formats

### Metadata Template (survey-phq9.json)
This is a **sidecar JSON** file that defines:
- `General` / `Study` - Survey information
- `Technical` - Implementation details  
- `phq9_01` through `phq9_09` - Item metadata with descriptions and levels

**Naming Convention:** Templates follow `survey-<instrument>.json` pattern so PRISM can find them.

### Recipe (demo/workshop/recipes/surveys/phq9.json)
This is a **recipe JSON** file that defines:
- `Survey` - Instrument metadata
- `Transforms` - Reverse coding rules (if any)
- `Scores` - Calculation methods (sum, mean, formula)

**Location:** Recipes must be in `recipes/surveys/` to be accessible by PRISM.

## Key Differences

| Template | Recipe |
|----------|--------|
| Describes **what** the data means | Defines **how** to calculate scores |
| One per data file (sub-01_*_survey.json) | One per instrument (phq9.json) |
| Located with data files | Located in recipes/ folder |
| Used during data collection/entry | Used during analysis/scoring |

## Folder Organization

This structure follows PRISM conventions:

- **`survey/`** - For questionnaires, interviews, behavioral tasks
- **`biometrics/`** - For physical measurements, anthropometry, fitness tests

Future additions might include:
- `physiological/` - For heart rate, blood pressure, etc.
- `imaging/` - For scan metadata

## Customization

Feel free to modify these files for your needs:
- Change language from "en" to "de", "fr", etc.
- Add study-specific instructions
- Adjust scoring rules if using a modified version
- Add additional metadata fields

## For Instructors

Before the workshop:
- [ ] Verify `survey-phq9.json` is present in `library/survey/`
- [ ] Verify `demo/workshop/recipes/surveys/phq9.json` exists
- [ ] Test PRISM can find the template (check conversion page)
- [ ] Test recipe with sample data
- [ ] Confirm all paths in instructions match actual structure

---

**Location in workshop:** `demo/workshop/library/`  
**Related folders:** 
- `../../library/survey/` - Main PRISM library (institution-wide)
- `demo/workshop/recipes/surveys/` - Workshop-local recipes (used in exercises)
