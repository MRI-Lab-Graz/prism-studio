# PRISM Workshop Demo Data

This folder contains materials for the PRISM hands-on workshop. The workshop teaches participants how to use the PRISM GUI to convert raw data, create metadata, and export analysis-ready outputs.

## Contents

### 1. `raw_material/`
**Purpose:** Starting point for Exercise 1 (Raw Data Conversion)

-**Current Files:**
- `participants_raw.tsv` - Demographic information (to become `participants.tsv`)
- `phq9_scores.tsv` - PHQ-9 depression questionnaire responses (tab-delimited file with columns `phq9_01` through `phq9_09` to match the metadata template)

**Status:** ✓ Ready for workshop use

**Recommendations for Improvement:**
- **Add more participants:** Current file has only 3 participants. Recommend 10-15 for better workshop experience.
- **Column naming:** Check if column names follow expected pattern (`phq9_01`, `phq9_02`, etc. vs `PHQ1`, `PHQ2`)
- **Add GAD-7 data:** Include `gad7_anxiety.csv` for bonus exercises
- **Add session column:** Optional - allows teaching multi-session concepts

**Expected Column Format for PHQ-9 (tab-delimited, shown as CSV for readability):**
```csv
participant_id,session,phq9_01,phq9_02,phq9_03,phq9_04,phq9_05,phq9_06,phq9_07,phq9_08,phq9_09
sub-01,ses-01,1,0,1,2,0,1,0,0,0
sub-02,ses-01,3,2,3,2,1,2,3,2,1
...
```

The actual `phq9_scores.tsv` file is tab-delimited, but the values are shown above as comma-separated for readability.

Or simpler format (converter can add `ses-01` automatically):
```csv
ID,phq9_01,phq9_02,phq9_03,phq9_04,phq9_05,phq9_06,phq9_07,phq9_08,phq9_09
sub-01,1,0,1,2,0,1,0,0,0
sub-02,3,2,3,2,1,2,3,2,1
...
```

---

### 2. `messy_dataset/`
**Purpose:** Legacy materials from old workshop (validation & fixing exercises)

**Current Use:** Not used in new workshop plan

**Status:** ⚠️ Can be kept for reference but not part of main workshop flow

**Notes:**
- Old workshop focused on fixing an already-structured dataset
- New workshop focuses on creating a dataset from scratch
- Can be used as a bonus "troubleshooting" exercise if time permits

---

### 3. `valid_dataset/`
**Purpose:** Reference implementation - completed example for participants to compare

**Status:** ⚠️ Needs to be created/updated

**Should Contain:**
A fully completed PRISM dataset that participants can reference, including:
```
valid_dataset/
├── dataset_description.json
├── participants.tsv
├── participants.json
├── README (optional - describes the dataset)
└── sub-01/
    └── ses-01/
        └── survey/
            ├── sub-01_ses-01_task-phq9_survey.tsv
            └── sub-01_ses-01_task-phq9_survey.json (FULLY annotated!)
└── sub-02/
    └── ses-01/
        └── survey/
            ├── sub-02_ses-01_task-phq9_survey.tsv
            └── sub-02_ses-01_task-phq9_survey.json
... (more subjects)
```

**Key Requirement:** The JSON sidecars must be **fully annotated** with:
- Complete `General` section (Name, Description, Instructions)
- Complete `Technical` section (Version, Language, Format)
- Full item-level metadata (Description and Levels for all PHQ-9 items)

This serves as the "answer key" for Exercise 2.

---

## Required Supporting Files (Outside demo/workshop/)

### 1. Library Template: `library/survey/survey-phq9.json`
**Purpose:** Reusable template for PHQ-9 metadata (Exercise 2)

**Status:** Check if exists

**Should Include:**
```json
{
  "General": {
    "Name": "Patient Health Questionnaire-9",
    "Description": "9-item self-report questionnaire for depression screening and severity measurement",
    "Instructions": "Participants rated how often they experienced each symptom over the past 2 weeks using a 4-point scale",
    "TermURL": "https://www.phqscreeners.com/"
  },
  "Technical": {
    "Version": "1.0",
    "Language": "en",
    "Format": "survey",
    "LicenseType": "open"
  },
  "phq9_01": {
    "Description": "Little interest or pleasure in doing things",
    "Levels": {
      "0": "Not at all",
      "1": "Several days",
      "2": "More than half the days",
      "3": "Nearly every day"
    }
  },
  "phq9_02": {
    "Description": "Feeling down, depressed, or hopeless",
    "Levels": {
      "0": "Not at all",
      "1": "Several days",
      "2": "More than half the days",
      "3": "Nearly every day"
    }
  }
  ... (repeat for all 9 items using `phq9_03` through `phq9_09`)
}
```

### 2. Scoring Recipe: `demo/workshop/recipes/surveys/phq9.json`
**Purpose:** Automated scoring logic (Exercise 3)

**Status:** Check if exists

**Should Include:**
```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": {
    "Name": "Patient Health Questionnaire-9",
    "TaskName": "phq9",
    "Description": "9-item depression screening tool",
    "Citation": "Kroenke, K., Spitzer, R. L., & Williams, J. B. (2001). The PHQ-9. Journal of General Internal Medicine, 16(9), 606-613.",
    "URL": "https://www.phqscreeners.com/"
  },
  "Transforms": {
    "Invert": {
      "Items": [],
      "Scale": {"min": 0, "max": 3}
    }
  },
  "Scores": [
    {
      "Name": "phq9_total",
      "Method": "sum",
      "Items": ["phq9_01", "phq9_02", "phq9_03", "phq9_04", "phq9_05", "phq9_06", "phq9_07", "phq9_08", "phq9_09"],
      "Description": "Total depression severity score",
      "Range": {"min": 0, "max": 27},
      "Interpretation": {
        "0-4": "Minimal depression",
        "5-9": "Mild depression",
        "10-14": "Moderate depression",
        "15-19": "Moderately severe depression",
        "20-27": "Severe depression"
      },
      "Missing": "ignore",
      "Note": "Sum of all 9 items. Interpretation: 0-4=minimal, 5-9=mild, 10-14=moderate, 15-19=moderately severe, 20-27=severe"
    }
  ]
}
```

---

## Workshop Preparation Checklist

### Before the Workshop (Instructor Tasks):

- [ ] **Raw Data:**
  - [ ] Expand `phq9_scores.tsv` to 10-15 participants
  - [ ] Verify column names match expected format
  - [ ] Optional: Create `gad7_anxiety.csv` for bonus exercises
  - [ ] Ensure `participants_raw.tsv` has demographic data

- [ ] **Reference Dataset:**
  - [ ] Create/update `valid_dataset/` as a complete example
  - [ ] Ensure all JSON sidecars are fully annotated
  - [ ] Validate the dataset (should pass 100%)

- [ ] **Library & Recipes:**
  - [ ] Verify `library/survey/survey-phq9.json` exists and is complete
  - [ ] Verify `demo/workshop/recipes/surveys/phq9.json` exists and is tested
  - [ ] Optional: Add `library/survey/gad7.json` and `demo/workshop/recipes/surveys/gad7.json`

- [ ] **Software:**
  - [ ] Test the converter with `phq9_scores.tsv`
  - [ ] Test the recipes/scoring with the valid_dataset
  - [ ] Verify SPSS export works (check `pyreadstat` installation)

- [ ] **Reset Script:**
  - [ ] Create a script to reset demo data between workshop sessions
  - [ ] Backup original `raw_material/` files
  - [ ] Script should delete any created `my_prism_dataset/` folders

---

## Suggested Enhancements (Future)

### Additional Raw Data Examples:
1. **Multi-session data:** 
  - `phq9_scores_longitudinal.tsv` with `visit` column (baseline, followup1, followup2)
   - Teaches session handling

2. **Different survey formats:**
  - Wide format (one row per participant, columns like `phq9_01_T1`, `phq9_01_T2`)
  - Shows converter flexibility

3. **Real-world messiness:**
   - Missing values (empty cells)
   - Inconsistent participant IDs (`sub01` vs `sub-01`)
  - Column name variations (`PHQ_01` vs `phq9_01`)
   - Extra columns that should be ignored

### Alternative Instruments:
- **GAD-7** (anxiety) - 7 items, same scale as PHQ-9
- **PSS-10** (stress) - 10 items, some reverse-coded (teaches `Transforms.Invert`)
- **PSQI** (sleep quality) - More complex scoring with subscales

### Advanced Workshop Module:
- **Physiological data:** Simple heart rate or blood pressure data
- **Biometrics:** Anthropometric measurements (height, weight, BMI calculation)
- **Multi-modal:** Combining survey + biometric data in recipes

---

## Testing the Workshop Flow

### Quick Test (15 minutes):
1. **Conversion Test:**
   ```bash
   # Start PRISM Studio
   python prism-studio.py
   
  # In GUI: Converter → Upload phq9_scores.tsv
   # Verify it creates proper BIDS structure
   ```

2. **Validation Test:**
   ```bash
   # In GUI: Validator → Select created dataset
   # Should show warnings about missing metadata (expected!)
   ```

3. **Recipe Test:**
   ```bash
   # In GUI: Recipes → Select dataset → Run phq9 recipe
   # Verify .sav file is created with proper labels
   ```

### Full Workshop Run-through (2 hours):
- Follow [WORKSHOP_HANDOUT.md](../../docs/WORKSHOP_HANDOUT.md) step-by-step
- Note any confusing steps or missing information
- Time each exercise to ensure 2-hour target is met

---

## Contact & Support

For workshop-related questions:
- **Documentation:** See `docs/WORKSHOP_PLAN.md` and `docs/WORKSHOP_HANDOUT.md`
- **Issues:** GitHub Issues
- **Email:** [instructor contact]

---

**Last Updated:** 2026-01-11  
**Workshop Version:** 2.0 (GUI-focused)
