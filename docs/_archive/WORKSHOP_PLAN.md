# PRISM Hands-on Workshop Strategy (2 Hours)

This document outlines the strategy for a 2-hour hands-on workshop designed to introduce new users to PRISM using the graphical interface (PRISM Studio).

**Workshop Theme:** Wellbeing Survey Analysis (WHO-5 Well-Being Index)

## Workshop Objectives
Participants will learn to:
- Apply YODA principles for organized, reproducible research projects
- Convert raw survey data (Excel) to BIDS/PRISM format
- Create comprehensive JSON metadata (sidecars) for documentation
- Use recipes to calculate scores and export to SPSS
- Complete the entire workflow using only the GUI - no command line required

## Target Audience
Researchers in psychology and neuroscience who:
- Collect survey, behavioral, or biometric data
- Want to standardize their data for sharing and analysis
- Prefer visual interfaces over command-line tools
- Need to export data to statistical software (SPSS, R, Jamovi)
- Value reproducibility and open science practices

## Schedule (Total: 120 Minutes)

| Time | Duration | Activity | Description |
| :--- | :--- | :--- | :--- |
| **00:00** | 10 min | **Introduction** | Why data structure matters. BIDS basics and PRISM extensions. YODA principles for project organization. |
| **00:10** | 15 min | **Exercise 0: Project Setup** | Create YODA-structured project. Understanding sourcedata/, rawdata/, code/, derivatives/ folders. |
| **00:25** | 30 min | **Exercise 1: Data Conversion** | Convert `wellbeing.xlsx` to BIDS/PRISM. Map columns, generate BIDS structure, understand file naming. |
| **00:55** | 10 min | **Break** | Coffee and informal Q&A. |
| **01:05** | 25 min | **Exercise 2: Metadata & Validation** | Add item descriptions and response labels. Copy from template library. Validate dataset. |
| **01:30** | 20 min | **Exercise 3: Recipes & Export** | Apply wellbeing recipe to calculate total scores. Export to SPSS with value labels. |
| **01:50** | 10 min | **Wrap-up & Resources** | Review complete workflow. Where to find help. How to use with own data. |

---

## Detailed Hands-on Scenarios

### Exercise 0: Project Setup with YODA (15 min)
**Goal:** Create an organized research project following YODA principles

**Concept: YODA (Yet anOther Data Analysis)**
- **sourcedata/** - Original files (preserved, never modified)
- **rawdata/** - Standardized BIDS/PRISM format
- **code/** - Analysis scripts (Python, R, etc.)
- **derivatives/** - Results and processed outputs

**GUI Steps:**
1. **Navigate to Projects**
   - Click "Projects" in PRISM Studio sidebar
   - URL: http://localhost:5001/projects

2. **Create New Project**
   - Project Name: `Wellbeing_Study_Workshop`
   - Location: Choose directory (Desktop, Documents, etc.)
   - Template: "YODA Structure" (if available)
   - Click "Create & Activate"

3. **Verify Structure**
   - Explore created folders in file browser
   - Understand purpose of each directory
   - Check "Active Project" indicator at top of screen

**Learning Outcomes:**
- Understand importance of project organization
- Recognize YODA folder structure
- Know where different file types belong
- Appreciate separation of raw data from analysis

---

### Exercise 1: Convert Raw Survey Data (30 min)
**Goal:** Transform `wellbeing.xlsx` into BIDS/PRISM format

**Starting Material:** `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`

**File Contents:**
- `participant_id` - Subject IDs (DEMO001, DEMO002, ...)
- `session` - Session labels (baseline)
- Demographics: `age`, `sex`, `education`, `handedness`
- Survey items: `WB01` through `WB05` (WHO-5 items, 0-5 scale)
- `completion_date` - When survey was completed

**WHO-5 Well-Being Index:**
- 5 items measuring subjective wellbeing
- Response scale: 0 (At no time) to 5 (All of the time)
- Total score range: 5-35 (higher = better wellbeing)
- Scores <13 suggest depression screening indicated

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
   - **Format:** "SPSS (.save - contains Levels/Labels)"
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
     - Creates output file: `recipes/surveys/phq9/phq9.save`

5. **Review Outputs**
   - Preview results in the GUI (table view)
   - Download `.save` file
   - Inspect codebook files:
     - `phq9_codebook.json` - machine-readable metadata
     - `phq9_codebook.tsv` - human-readable variable documentation
     - `methods_boilerplate.md` - auto-generated methods section text

6. **Open in SPSS/Jamovi**
   - Demonstrate opening the `.save` file
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
