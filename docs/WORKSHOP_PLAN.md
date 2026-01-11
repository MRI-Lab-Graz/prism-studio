# PRISM Hands-on Workshop Strategy (2 Hours)

This document outlines the strategy for a 2-hour hands-on workshop designed to introduce new users to PRISM using the graphical interface (PRISM Studio).

## Workshop Objectives
Participants will learn to:
- Understand data structure fundamentals in BIDS and PRISM
- Prepare raw data files and convert them to BIDS/PRISM format
- Create basic JSON metadata templates (sidecars)
- Use recipes to generate analysis-ready outputs (SPSS, Excel, CSV)
- Complete the entire workflow using only the GUI - no command line required

## Target Audience
Researchers in psychology and neuroscience who:
- Collect survey, behavioral, or biometric data
- Want to standardize their data for sharing and analysis
- Prefer visual interfaces over command-line tools
- Need to export data to statistical software (SPSS, R, Jamovi)

## Schedule (Total: 120 Minutes)

| Time | Duration | Activity | Description |
| :--- | :--- | :--- | :--- |
| **00:00** | 15 min | **Introduction** | Theory: Why data structure matters. BIDS basics and PRISM extensions. The hierarchy concept (Dataset → Subject → Session → Files). |
| **00:15** | 10 min | **GUI Setup & Tour** | Launch PRISM Studio. Tour of main sections: Home, Projects, Converter, Library, Recipes. |
| **00:25** | 30 min | **Hands-on 1: Raw to BIDS** | Convert raw CSV/Excel data to BIDS structure. Map columns, generate files, and validate. Learn about file naming conventions. |
| **00:55** | 10 min | **Break** | Coffee and informal Q&A. |
| **01:05** | 25 min | **Hands-on 2: JSON Templates** | Create and edit JSON sidecars. Understand required vs. optional metadata fields. Use the template editor and library. |
| **01:30** | 20 min | **Hands-on 3: Recipes & Export** | Apply recipes to calculate scores and subscales. Export to SPSS (.sav) with value labels. Preview results in Excel. |
| **01:50** | 10 min | **Wrap-up & Resources** | Review of workflow. Where to find help. How to contribute templates. Next steps for their own data. |

---

## Detailed Hands-on Scenarios

### Scenario 1: From Raw Data to BIDS Structure (25-30 min)
**Goal:** Transform unstructured research data into a valid PRISM dataset.

**Starting Materials:** `demo/workshop/exercise_1_raw_to_bids/raw_data/`
- `participants_raw.tsv` (tab-delimited, matches template column IDs)
- `phq9_scores.tsv` (tab-delimited, columns `phq9_01`–`phq9_09`)
**Backup Copies:** `demo/workshop/raw_material/`
- `participants_raw.csv`
- `phq9_scores.csv`
- Maybe additional: `gad7_anxiety.xlsx`, `sleep_diary.csv`

**GUI Steps:**
1. **Open Converter Tool**
   - Navigate to "Converter" in PRISM Studio
   - Select "Raw Data to BIDS/PRISM"

2. **Load Raw Data**
   - Upload or browse to `demo/workshop/exercise_1_raw_to_bids/raw_data/phq9_scores.tsv`
   - System detects columns and data types

3. **Map to BIDS Structure**
   - Assign participant ID column (e.g., `ID` → `participant_id`)
   - Assign session if available (e.g., `visit` → `session`)
   - Select survey/task name: `phq9`
   - Choose modality: `survey`

4. **Configure Output**
   - Set output directory (creates proper folder structure automatically)
   - Choose filename pattern: `sub-{id}_ses-{session}_task-phq9_survey.tsv`
   - Preview the structure before generating

5. **Generate & Validate**
   - Click "Convert" - system creates:
     - `sub-01/ses-01/survey/sub-01_ses-01_task-phq9_survey.tsv`
     - Corresponding `.json` sidecar (basic template)
     - `participants.tsv` from demographics
     - `dataset_description.json`
   - Run quick validation to ensure structure is correct

**Learning Outcomes:**
- Understand BIDS folder hierarchy
- Learn proper file naming with `sub-`, `ses-`, `task-` entities
- See how metadata flows from source to structure

---

### Scenario 2: Creating JSON Metadata Templates (25 min)
**Goal:** Enrich data with proper metadata using JSON sidecars.

**Starting Point:** The dataset created in Scenario 1 (or `demo/workshop/messy_dataset/`)

**GUI Steps:**
1. **Open Template Editor**
   - Navigate to "Library" → "Template Editor"
   - Or use the inline editor in the validation results

2. **Edit Survey Sidecar**
   - Open `sub-01_ses-01_task-phq9_survey.json`
   - Fill in required PRISM fields:
     - `General.Name`: "Patient Health Questionnaire-9"
     - `General.Description`: "9-item depression screening tool"
     - `General.Instructions`: How participants completed it
   - Add technical details:
     - `Technical.Version`: "1.0"
     - `Technical.Language`: "en"

3. **Add Item-Level Metadata**
   - For each column (PHQ9_1, PHQ9_2, etc.), add:
     - `Description`: Question text (e.g., "Little interest or pleasure in doing things")
     - `Levels`: Response scale coding
       ```json
       "Levels": {
         "0": "Not at all",
         "1": "Several days",
         "2": "More than half the days",
         "3": "Nearly every day"
       }
       ```

4. **Use Library Templates**
   - Browse `library/survey/` for pre-made templates
   - If PHQ-9 template exists, copy relevant sections
   - Modify for your specific implementation

5. **Validate Metadata**
   - Run validation again
   - Check that schema errors are resolved
   - Verify that required fields are complete

**Learning Outcomes:**
- Understand JSON structure and hierarchy
- Distinguish between General, Technical, and item-level metadata
- Learn to use the library for reusable templates
- See how metadata improves data documentation

---

### Scenario 3: Scoring with Recipes & SPSS Export (20 min)
**Goal:** Generate analysis-ready outputs with calculated scores, exported to SPSS format.

**Starting Point:** Validated PRISM dataset with survey data

**GUI Steps:**
1. **Open Recipes & Scoring**
   - Navigate to "Recipes & Scoring" in PRISM Studio
   - Select your dataset folder

2. **Choose Recipe**
   - Select modality: `Survey`
   - Recipe filter: `phq9` (or leave empty to run all available)
   - Confirm the workshop supply at `demo/workshop/recipes/surveys/phq9.json` is available so the recipe can be copied into your dataset-level `recipes/surveys/` folder

3. **Configure Output**
   - **Format:** "SPSS (.sav - contains Levels/Labels)"
   - **Layout:** "Long (one row per session)" or "Wide (one row per participant)"
   - **Language:** "English" (for value labels)
   - **Options:**
     - ☐ Include Raw Data Columns (optional)
     - ☑ Generate Codebook

4. **Run Recipe**
   - Click "Run Scoring"
   - System processes:
     - Reads raw survey responses
     - Applies reverse coding (if specified in recipe)
     - Calculates total score and subscales
     - Creates output file: `recipes/surveys/phq9/phq9.sav`

5. **Review Outputs**
   - Preview results in the GUI (table view)
   - Download `.sav` file
   - Inspect codebook files:
     - `phq9_codebook.json` - machine-readable metadata
     - `phq9_codebook.tsv` - human-readable variable documentation
     - `methods_boilerplate.md` - auto-generated methods section text

6. **Open in SPSS/Jamovi**
   - Demonstrate opening the `.sav` file
   - Show that variable labels and value labels are preserved
   - Data is ready for immediate analysis

**Alternative: Excel Export**
- Change format to "Excel (.xlsx)"
- System creates multi-sheet workbook:
  - **Sheet 1 (Data):** Calculated scores
  - **Sheet 2 (Codebook):** Variable descriptions
  - **Sheet 3 (Survey Info):** Metadata from recipe

**Learning Outcomes:**
- Understand the recipe system for reproducible scoring
- See how reverse coding and subscales are automated
- Learn to export with full metadata preservation
- Appreciate the value of machine-readable scoring logic

---

## Recipe Example: PHQ-9

For the workshop, ensure `demo/workshop/recipes/surveys/phq9.json` exists with:

```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": {
    "Name": "Patient Health Questionnaire-9",
    "TaskName": "phq9",
    "Description": "9-item depression screening tool",
    "Citation": "Kroenke, K., Spitzer, R. L., & Williams, J. B. (2001). The PHQ-9. Journal of General Internal Medicine, 16(9), 606-613."
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
      "Items": ["phq9_1", "phq9_2", "phq9_3", "phq9_4", "phq9_5", "phq9_6", "phq9_7", "phq9_8", "phq9_9"],
      "Description": "Total depression severity score",
      "Range": {"min": 0, "max": 27},
      "Interpretation": {
        "0-4": "Minimal depression",
        "5-9": "Mild depression",
        "10-14": "Moderate depression",
        "15-19": "Moderately severe depression",
        "20-27": "Severe depression"
      },
      "Missing": "ignore"
    }
  ]
}
```

---

## Technical Setup for Instructor

### Before the Workshop:
1. **Environment Check:**
   - Ensure Python environment is activated: `source .venv/bin/activate`
   - Launch PRISM Studio: `python prism-studio.py`
   - Verify it's accessible at `http://localhost:5001`

2. **Demo Data Preparation:**
    - Verify `demo/workshop/raw_material/` contains the original CSV backups:
       - `participants_raw.csv` (10-15 sample participants)
      - `phq9_scores.tsv` (complete PHQ-9 responses ready for conversion)
    - Verify `demo/workshop/exercise_1_raw_to_bids/raw_data/` contains the working TSV files:
       - `participants_raw.tsv` (converted/tab-delim, matches template columns)
       - `phq9_scores.tsv` (tab-delimited, columns `phq9_01`–`phq9_09`)
       - Optionally: `gad7_anxiety.csv`, `demographics_extended.xlsx`
   - Create backup/reset script to restore clean state

3. **Library Setup:**
   - Ensure `library/survey/` contains templates:
     - `phq9.json` - complete PHQ-9 template
     - `gad7.json` - GAD-7 anxiety template
   - Ensure `recipes/surveys/` contains:
     - `phq9.json` - scoring recipe (see example above)

4. **Valid Reference Dataset:**
   - Have `demo/workshop/valid_dataset/` as a completed example
   - Participants can compare their work against this

### During the Workshop:
- **Screen Sharing:** Show the GUI clearly (consider zoom/font size)
- **Pacing:** Allow time for participants to complete each step
- **Troubleshooting:** Common issues:
  - File path confusion (absolute vs. relative)
  - Missing participants.tsv
  - Incorrect column mapping
  - JSON syntax errors (missing commas, quotes)

---

## Student Take-away

Participants will leave with:
1. **Conceptual Understanding:**
   - BIDS/PRISM folder structure and naming conventions
   - Role of metadata in reproducible research
   - Difference between raw data, structured data, and derivatives

2. **Practical Skills:**
   - Convert raw data to BIDS using the GUI
   - Create and edit JSON metadata templates
   - Apply recipes for automated scoring
   - Export analysis-ready data to SPSS/Excel

3. **Resources:**
   - [WORKSHOP_HANDOUT.md](WORKSHOP_HANDOUT.md) - step-by-step guide
   - Access to `demo/workshop/valid_dataset/` - reference implementation
   - Links to:
     - PRISM documentation
     - Recipe library on GitHub
     - Community forum for questions

4. **Next Steps:**
   - Apply workflow to their own research data
   - Contribute templates to the library
   - Share validated datasets with collaborators
   - Use PRISM for data archiving and publication
