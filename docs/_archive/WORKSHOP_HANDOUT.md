# PRISM Workshop Handout: Wellbeing Survey Analysis

Welcome to the PRISM Hands-on Workshop! This handout contains all the step-by-step instructions you need to complete the workshop exercises using the graphical interface (PRISM Studio).

**Workshop Goals:**
- Set up a research project following YODA principles
- Convert raw wellbeing survey data (Excel) to BIDS/PRISM structure
- Create proper JSON metadata (sidecars)
- Use recipes to calculate wellbeing scores and export to SPSS

**Example Dataset:** WHO-5 Well-Being Index survey data  
**All tasks will be completed through the GUI - no command line required!**

---

## 0. Workshop Overview

This workshop follows a complete research data workflow:

| Exercise | Task | Time | Outcome |
|----------|------|------|---------|
| **0** | Project Setup (YODA) | 15 min | Organized project structure |
| **1** | Convert Raw Data | 30 min | PRISM-formatted dataset |
| **2** | Validate & Fix Metadata | 25 min | Complete, valid metadata |
| **3** | Apply Recipes & Export | 20 min | SPSS file with calculated scores |

---

## 1. Setup & Access

### Launching PRISM Studio

**Windows Users:**
1. Locate the **`PrismValidator.exe`** file
2. Double-click to launch
3. Your browser should open to: **`http://localhost:5001`**

**If you installed from source:**
```powershell
# Windows PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
python prism-studio.py
```

```bash
# macOS/Linux
source .venv/bin/activate
python prism-studio.py
```

Open your browser and navigate to: **`http://localhost:5001`**

**Using a shared workshop server:**
Your instructor will provide the URL (e.g., `http://workshop-server:5001`)

---

## 2. Exercise 0: Project Setup with YODA

**Time:** ~15 minutes  
**Goal:** Create an organized research project following YODA principles

### What is YODA?

**YODA** (Yet anOther Data Analysis) is a project organization framework:
- **Separates** raw data, analysis code, and results
- **Preserves** original data files (never modified)
- **Enables** reproducibility and version control
- **Simplifies** collaboration and sharing

### Step-by-Step: Create Your Project

#### Step 1: Navigate to Projects Page
1. In PRISM Studio, click on **"Projects"** in the sidebar
2. Or go to: **http://localhost:5001/projects**

#### Step 2: Create New Project
1. Find the **"Create New Project"** section
2. **Project Name:** `Wellbeing_Study_Workshop`
3. **Location:** Choose a folder (e.g., Desktop or Documents)
4. **Template:** Select **"YODA Structure"** (if available)
5. Click **"Create & Activate"**

#### Step 3: Review the Structure
Your project now has this folder structure:
```
Wellbeing_Study_Workshop/
├── sourcedata/          # Original Excel/CSV files (never edit!)
├── rawdata/             # PRISM-formatted BIDS data
│   ├── dataset_description.json
│   └── participants.tsv
├── code/                # Analysis scripts
├── derivatives/         # Computed results (scores, SPSS exports)
└── README.md
```

**What goes where:**
- **sourcedata/** - Your original `wellbeing.xlsx` file
- **rawdata/** - Converted PRISM format (Exercise 1)
- **derivatives/** - Calculated scores and exports (Exercise 3)

#### Step 4: Verify Active Project
Check that the top of the screen shows: **Active Project: Wellbeing_Study_Workshop**

**✓ Exercise 0 Complete!** You now have a properly organized research project.

---

## 3. Exercise 1: Converting Raw Data to PRISM

**Time:** ~30 minutes  
**Goal:** Transform Excel wellbeing survey data into BIDS/PRISM format

### Starting Materials
Location: `examples/workshop/exercise_1_raw_data/raw_data/`
- **wellbeing.xlsx** (or wellbeing.tsv) - WHO-5 survey responses

**File contents:**
- `participant_id` - Subject identifiers (DEMO001, DEMO002, ...)
- `session` - Session labels (baseline)
- Demographics: `age`, `sex`, `education`, `handedness`
- Survey items: `WB01`, `WB02`, `WB03`, `WB04`, `WB05`
- `completion_date` - When survey was completed
- `demo/workshop/raw_material/participants_raw.csv`
- `demo/workshop/raw_material/phq9_scores.csv`

### Step-by-Step: Converting PHQ-9 Data

#### Step 1: Open the Converter Tool
1. Click on **"Converter"** in the navigation menu
2. You'll see several conversion options
3. Select **"Raw Data to BIDS"** or **"Survey Data Converter"**

#### Step 2: Upload Raw Data File
1. Click **"Browse"** or **"Choose File"**
2. Navigate to `demo/workshop/exercise_1_raw_to_bids/raw_data/phq9_scores.tsv`
3. Click **"Upload"** or **"Load File"**
4. The system will display a preview of your data

#### Step 3: Map Columns to BIDS Structure
The converter will show you the columns from your CSV. You need to map them:

**Required Mappings:**
- **Participant ID Column:** 
  - Find the column containing subject IDs (e.g., `SubjectID`, `ID`, `participant`)
  - Select it from the dropdown: "This column represents → `participant_id`"
  
- **Session Column (if applicable):**
  - If you have multiple visits/sessions, select that column
  - Map to → `session`
  - If no sessions, the system will use `ses-01` by default

**Survey-Specific Settings:**
- **Task/Survey Name:** Enter `phq9`
  - This will be used in filenames: `task-phq9`
- **Modality:** Select `survey`
- **File Suffix:** Keep as `survey` (or legacy `beh`)

**Data Columns:**
- The remaining columns (phq9_1, phq9_2, ... phq9_9) will be preserved as data columns
- Check the preview to ensure column names are valid (no spaces, special characters)

#### Step 4: Configure Output Settings
1. **Output Directory:** 
   - Click **"Set Output Folder"**
   - Choose or create: `demo/workshop/my_prism_dataset/`
   
2. **Filename Pattern Preview:**
   - System shows: `sub-{id}_ses-{session}_task-phq9_survey.tsv`
   - Verify this looks correct

3. **Options:**
   - ☑ **Generate sidecars** (JSON files) - Keep checked
   - ☑ **Create participants.tsv** - Keep checked
   - ☑ **Create dataset_description.json** - Keep checked

#### Step 5: Convert!
1. Click **"Convert to BIDS"** or **"Generate Dataset"**
2. Progress bar will show file creation
3. When complete, you'll see a success message:
   - ✓ Created 15 files
   - ✓ Structure validated
   - ✓ No critical errors

#### Step 6: Review the Generated Structure
Click **"View Generated Files"** or navigate to your output folder:

```
my_prism_dataset/
├── dataset_description.json
├── participants.tsv
└── sub-01/
    └── ses-01/
        └── survey/
            ├── sub-01_ses-01_task-phq9_survey.tsv
            └── sub-01_ses-01_task-phq9_survey.json
└── sub-02/
    └── ses-01/
        └── survey/
            ├── sub-02_ses-01_task-phq9_survey.tsv
            └── sub-02_ses-01_task-phq9_survey.json
... (more subjects)
```

**Key Learning Points:**
- ✓ BIDS uses a hierarchical folder structure: Dataset → Subject → Session → Modality
- ✓ Every data file (`.tsv`) has a companion metadata file (`.json`)
- ✓ File naming follows strict patterns: `sub-<id>_ses-<id>_task-<name>_<suffix>.<ext>`
- ✓ The system prevents common naming errors automatically

---

## 3. Exercise 2: Creating & Editing JSON Metadata

**Time:** ~25 minutes  
**Goal:** Add proper metadata to make your data self-documenting and reusable

### Step-by-Step: Enriching Survey Metadata

#### Step 1: Validate Your Dataset
1. Go to **"Home"** or **"Validator"**
2. Click **"Select Dataset"** and choose `demo/workshop/my_prism_dataset/`
3. Click **"Validate Dataset"**
4. You'll likely see warnings like:
   - ⚠️ Missing required field: `General.Name`
   - ⚠️ Missing field: `General.Description`
   - ℹ️ Recommended: Add `Technical.Language`

This is expected! The converter created basic sidecars, but we need to fill in survey-specific metadata.

#### Step 2: Open the JSON Editor
From the validation results page:
1. Find a survey file: `sub-01_ses-01_task-phq9_survey.json`
2. Click the **"Edit"** or **📝 (pencil icon)** button
3. The JSON editor will open

**Alternative path:**
- Go to **"Library"** → **"Template Editor"**
- Browse to your file
- Click **"Edit Template"**

#### Step 3: Fill in General Metadata
You'll see a structured form (or JSON editor). Fill in these fields:

**General Section:**
```json
"General": {
  "Name": "Patient Health Questionnaire-9",
  "Description": "9-item self-report questionnaire for depression screening and severity measurement",
  "Instructions": "Participants rated how often they experienced each symptom over the past 2 weeks"
}
```

**In the GUI:**
- **Name:** Enter in the text field: `Patient Health Questionnaire-9`
- **Description:** Enter: `9-item self-report questionnaire for depression screening`
- **Instructions:** Enter how participants completed the survey

#### Step 4: Add Technical Metadata

**Technical Section:**
```json
"Technical": {
  "Version": "1.0",
  "Language": "en",
  "Format": "survey",
  "LicenseType": "open"
}
```

**In the GUI:**
- Expand the **"Technical"** accordion/section
- **Version:** `1.0`
- **Language:** Select `en` from dropdown (or enter)
- **Format:** `survey`

#### Step 5: Add Item-Level Metadata (Column Descriptions)
This is the most detailed part but also the most valuable!

For each PHQ-9 item, you'll add:
- **Description:** The actual question text
- **Levels:** Response scale coding (what each number means)

**Example for item PHQ9_1:**

In the GUI, find the **"Column Metadata"** or **"Items"** section:

1. Click **"Add Column"** or find `phq9_1` in the list
2. Fill in:

**Description:** `Little interest or pleasure in doing things`

**Levels** (click "Add Level" for each):
- Code: `0` → Label: `Not at all`
- Code: `1` → Label: `Several days`
- Code: `2` → Label: `More than half the days`
- Code: `3` → Label: `Nearly every day`

**Repeat for all 9 items:**

<details>
<summary>📋 Click to expand: All PHQ-9 items</summary>

- **phq9_1:** Little interest or pleasure in doing things
- **phq9_2:** Feeling down, depressed, or hopeless
- **phq9_3:** Trouble falling or staying asleep, or sleeping too much
- **phq9_4:** Feeling tired or having little energy
- **phq9_5:** Poor appetite or overeating
- **phq9_6:** Feeling bad about yourself - or that you are a failure or have let yourself or your family down
- **phq9_7:** Trouble concentrating on things, such as reading the newspaper or watching television
- **phq9_8:** Moving or speaking so slowly that other people could have noticed. Or the opposite - being so fidgety or restless that you have been moving around a lot more than usual
- **phq9_9:** Thoughts that you would be better off dead, or of hurting yourself in some way

(All use the same 0-3 scale as above)
</details>

**Time-Saving Tip:** Use the Library!
- If `library/survey/survey-phq9.json` exists, you can:
  1. Go to **"Library"**
  2. Find **"PHQ-9"** template
  3. Click **"Copy to Clipboard"** or **"Use as Template"**
  4. Paste/apply to your file
  5. Modify if needed for your specific implementation

#### Step 6: Save and Re-Validate
1. Click **"Save"** in the editor
2. Go back to **"Validator"**
3. Click **"Re-validate"**
4. Warnings should be resolved! ✓

**Key Learning Points:**
- ✓ JSON sidecars make data self-documenting
- ✓ Metadata hierarchy: General → Technical → Item-level
- ✓ Value labels (Levels) are crucial for statistical software
- ✓ Templates save time and ensure consistency

---

## 4. Exercise 3: Recipes & SPSS Export

**Time:** ~20 minutes  
**Goal:** Calculate total scores and export analysis-ready data to SPSS with full metadata

### Step-by-Step: Automated Scoring & Export

#### Step 1: Verify Recipe Exists
Before we begin, ensure the PHQ-9 scoring recipe exists:
1. Go to the workshop materials inside this repo
2. Check: `demo/workshop/recipes/surveys/phq9.json`
3. If it doesn't exist, your instructor will provide it (or it's in the workshop materials)

**What's in a recipe?**
A recipe defines:
- Which items to sum/average
- Reverse coding rules (if needed)
- Subscale calculations
- Interpretation categories (mild, moderate, severe)

#### Step 2: Open Recipes & Scoring
1. Click **"Recipes & Scoring"** in the navigation menu
2. You'll see the main scoring interface

#### Step 3: Select Your Dataset
1. **Dataset Folder:** 
   - Click **"Browse"** next to "PRISM Dataset Folder"
   - Select: `demo/workshop/my_prism_dataset/`
   - Or if you have a project loaded, it may auto-populate

2. System will validate that it's a proper PRISM dataset
   - ✓ Must have `dataset_description.json`
   - ✓ Must have valid BIDS structure

#### Step 4: Configure Recipe Settings

**Modality:**
- Select: **`Survey`**
- (This tells the system to look in `recipes/surveys/`)

**Recipe Filter:**
- Enter: `phq9`
- Or leave empty to run all available recipes

**Output Format:**
- Select: **`SPSS (.save - contains Levels/Labels)`**
- This is the key format for preserving your metadata!

**Layout:**
- Select: **`Long (one row per session)`**
- Alternative: `Wide` creates one row per participant (useful for repeated measures)

**Language:**
- Select: **`English`**
- This affects variable labels in the output file

**Additional Options:**
- ☐ **Include Raw Data Columns** - Usually uncheck (we only want the calculated scores)
- ☑ **Generate Codebook** - Keep checked (creates documentation files)

#### Step 5: Run the Recipe
1. Click **"Run Scoring"** or **"Process Dataset"**
2. Progress indicator will show:
   - 📊 Processing recipe: phq9
   - 📝 Reading survey files...
   - 🧮 Calculating scores...
   - 💾 Writing outputs...
3. Success message: "✓ Processed 15 files, generated 1 output file"

#### Step 6: Review Outputs
The system creates several files in your dataset:

```
my_prism_dataset/
└── recipes/
    └── surveys/
        ├── dataset_description.json
        └── phq9/
            ├── phq9.save                    ← SPSS file with data + metadata
            ├── phq9_codebook.json          ← Machine-readable metadata
            ├── phq9_codebook.tsv           ← Human-readable codebook
            └── methods_boilerplate.md      ← Auto-generated methods text
```

**In the GUI:**
- Click **"View Results"** or **"Download Outputs"**
- You'll see a preview table with the calculated scores

**Preview should show:**
| participant_id | session | phq9_total |
|----------------|---------|------------|
| sub-01         | ses-01  | 12         |
| sub-02         | ses-01  | 7          |
| sub-03         | ses-01  | 15         |
| ...            | ...     | ...        |

#### Step 7: Download and Open in SPSS
1. Click **"Download SPSS File"** or navigate to the file
2. Download `phq9.save`
3. Open in SPSS (or Jamovi, or PSPP - any software that reads `.save` files)

**What you'll see in SPSS:**
- **Variable View:**
  - `participant_id` - Label: "Participant identifier"
  - `session` - Label: "Session identifier"
  - `phq9_total` - Label: "Total depression severity score"
  
- **Value Labels (automatically applied):**
  - No need to define them manually!
  - If using interpretation categories, they'll be coded:
    - 1 = "Minimal depression" (0-4)
    - 2 = "Mild depression" (5-9)
    - 3 = "Moderate depression" (10-14)
    - 4 = "Moderately severe depression" (15-19)
    - 5 = "Severe depression" (20-27)

**Data is immediately ready for analysis!**
- Run descriptives: `DESCRIPTIVES VARIABLES=phq9_total.`
- No need to manually recode or label anything
- Perfect for sharing with collaborators

#### Step 8 (Optional): Try Excel Export
Go back to the Recipes interface and change:
- **Output Format:** Select `Excel (.xlsx)`
- Click **"Run Scoring"** again

**Excel output creates a multi-sheet workbook:**
- **Sheet 1 - Data:** The actual scores
- **Sheet 2 - Codebook:** Variable descriptions and value labels
- **Sheet 3 - Survey Info:** Metadata (survey name, version, citation, etc.)

This format is great for:
- Quick visual inspection
- Sharing with non-SPSS users
- Including in supplementary materials

#### Step 9: Review the Methods Boilerplate
1. Navigate to: `recipes/surveys/methods_boilerplate.md`
2. Open the file (or view in GUI if available)
3. You'll see auto-generated text describing your scoring procedures:

**Example:**
> Data were organized and validated according to the PRISM standard. Data processing and score calculation were performed automatically using the PRISM system, applying the scoring logic defined in machine-readable JSON recipes.
>
> ### Patient Health Questionnaire-9
> 9-item self-report questionnaire for depression screening and severity measurement.
>
> **Scoring:**
> - `phq9_total`: sum score (9 items).

**This text can be copied directly into your Methods section!**

**Key Learning Points:**
- ✓ Recipes automate scoring (reproducible, no manual Excel formulas)
- ✓ SPSS export preserves all metadata (variable labels, value labels)
- ✓ Multiple output formats for different use cases
- ✓ Codebooks document the derivation process
- ✓ Methods text is auto-generated for publication

---

## 5. Bonus Exercises (If Time Permits)

### Bonus A: Add a Second Survey (GAD-7)
**Goal:** Practice the full workflow on a different instrument

1. **Convert Raw Data:**
   - Use `demo/workshop/raw_material/gad7_anxiety.csv` (if available)
   - Follow Exercise 1 steps
   - Task name: `gad7`

2. **Add Metadata:**
   - Use template from `library/survey/gad7.json` (if available)
   - Or manually add:
     - Name: "Generalized Anxiety Disorder-7"
     - 7 items about anxiety symptoms
     - Same 0-3 response scale as PHQ-9

3. **Run Recipe:**
   - Recipe file: `recipes/surveys/gad7.json`
   - Export to SPSS
   - Compare with PHQ-9 results

### Bonus B: Combine Multiple Surveys in One Export
**Goal:** Create a single analysis file with scores from multiple instruments

1. In **Recipes & Scoring:**
   - Recipe Filter: Leave **empty** (or enter: `phq9,gad7`)
   - Layout: Select **`Wide`**
   - Format: **`Excel (.xlsx)`** or **`CSV`**

2. Output will have columns:
   - `participant_id`
   - `phq9_total`
   - `gad7_total`
   - One row per participant (if single session)
   - Or: One row per participant with `ses-01_phq9_total`, `ses-01_gad7_total`, etc.

### Bonus C: Explore the Library
1. Navigate to **"Library"** in PRISM Studio
2. Browse available templates:
   - **Survey instruments:** PHQ-9, GAD-7, PSQI, PSS, etc.
   - **Biometric measures:** Blood pressure, anthropometry, etc.
3. Click on a template to view its structure
4. **Try creating your own:**
   - Click **"Create New Template"**
   - Choose modality: `survey`
   - Fill in metadata for a survey you use in your research
   - Save to library for reuse

---

## 6. Troubleshooting & Common Issues

### Issue 1: "Invalid filename pattern"
**Symptom:** Validation fails with filename errors

**Solution:**
- BIDS requires hyphens after entity labels: `sub-01` not `sub01`
- Use only lowercase letters, numbers, and hyphens in identifiers
- Check the pattern: `sub-<id>_ses-<id>_task-<name>_<suffix>.<ext>`

### Issue 2: "Missing required field: General.Name"
**Symptom:** Validation warnings about metadata

**Solution:**
- Open the JSON sidecar in the editor
- Ensure `General.Name` field exists and has a value
- Check for JSON syntax errors (missing commas, quotes)

### Issue 3: "Recipe not found: xyz"
**Symptom:** Scoring fails when trying to run a recipe

**Solution:**
- Check that `recipes/surveys/<name>.json` exists
- Recipe file name must match the task name in your data
- If missing, ask instructor or check the recipe library

### Issue 4: SPSS file won't open / missing labels
**Symptom:** `.save` file opens but labels are missing

**Solution:**
- Ensure you filled in the `Levels` field in your JSON metadata
- Try re-exporting with "Generate Codebook" checked
- Check that `pyreadstat` is installed (fallback to CSV if not)

### Issue 5: "Column not found" in recipe processing
**Symptom:** Recipe runs but scores are all `n/a`

**Solution:**
- Recipe expects specific column names (e.g., `phq9_1`, `phq9_2`)
- Check your TSV file column headers
- If different (e.g., `PHQ9_1`), either:
  - Rename columns in the converter settings, or
  - Edit the recipe to match your column names

---

## 7. Key Concepts Summary

### BIDS Structure Hierarchy
```
Dataset
├── dataset_description.json    (Required: describes the dataset)
├── participants.tsv            (Required: one row per participant)
├── participants.json           (Optional: column descriptions)
└── sub-<label>/               (One folder per participant)
    └── ses-<label>/           (One folder per session/visit)
        └── <modality>/        (survey, eeg, biometrics, etc.)
            ├── <data file>.tsv
            └── <data file>.json (sidecar)
```

### File Naming Entities
- **`sub-<label>`**: Participant/subject ID (required)
- **`ses-<label>`**: Session/visit ID (optional)
- **`task-<label>`**: Task or survey name (required for functional data)
- **`<suffix>`**: Modality indicator (`survey`, `physio`, `eeg`, etc.)
- **`<extension>`**: File type (`.tsv`, `.json`, `.nii.gz`, etc.)

### JSON Sidecar Hierarchy (PRISM)
```json
{
  "General": {          // Survey/task description
    "Name": "...",
    "Description": "...",
    "Instructions": "..."
  },
  "Technical": {        // Implementation details
    "Version": "...",
    "Language": "...",
    "Format": "..."
  },
  "item_name": {        // Column/variable metadata
    "Description": "...",
    "Levels": {
      "0": "Not at all",
      "1": "Several days",
      ...
    }
  }
}
```

### Recipe Components
1. **Metadata:** Survey name, version, citation
2. **Transforms:** Reverse coding rules
3. **Scores:** Calculation methods (sum, mean, formula)
4. **Interpretation:** Clinical cutoffs (optional)

---

## 8. Resources & Next Steps

### Documentation
- **PRISM Website:** [https://prism-standard.org](https://prism-standard.org) (if available)
- **GitHub Repository:** [https://github.com/MRI-Lab-Graz/prism-studio](https://github.com/MRI-Lab-Graz/prism-studio)
- **Full Documentation:** Check the `docs/` folder in your installation
  - `QUICK_START.md` - Getting started guide
  - `SPECIFICATIONS.md` - Technical details
  - `RECIPES.md` - Recipe system documentation

### Support & Community
- **GitHub Issues:** Report bugs or request features
- **Discussions:** Ask questions, share templates
- **Email Support:** (Instructor will provide)

### What to Do Next
1. **Apply to your data:**
   - Try converting one of your own datasets
   - Start with a small pilot dataset (5-10 participants)
   - Build your library of templates

2. **Contribute:**
   - Share your survey templates with the community
   - Contribute recipes for common instruments
   - Report any bugs or unclear documentation

3. **Integrate into workflow:**
   - Use PRISM early in data collection (not just at the end)
   - Create templates before data collection starts
   - Validate data regularly (not just once)

4. **Learn more:**
   - Explore advanced features (NeuroBagel export, FAIR checker)
   - Try the CLI for batch processing
   - Look into plugins for custom functionality

---

## 9. Workshop Files Reference

### Files You Created Today
- `demo/workshop/my_prism_dataset/` - Your converted dataset
- `demo/workshop/my_prism_dataset/recipes/surveys/` - Calculated scores

### Reference Files (Provided)
- `demo/workshop/valid_dataset/` - Completed example for comparison
   - `library/survey/survey-phq9.json` - PHQ-9 template
- `demo/workshop/recipes/surveys/phq9.json` - PHQ-9 scoring recipe

### Raw Data (Workshop Materials)
- `demo/workshop/exercise_1_raw_to_bids/raw_data/participants_raw.tsv`
- `demo/workshop/exercise_1_raw_to_bids/raw_data/phq9_scores.tsv`
### Backups (Original CSVs)
- `demo/workshop/raw_material/participants_raw.csv`
- `demo/workshop/raw_material/phq9_scores.csv`
- `demo/workshop/raw_material/gad7_anxiety.csv` (if available)

---

**Thank you for participating in the PRISM workshop!**

For questions or issues, please contact: [your-email@institution.edu]

*Happy data standardizing! 🎉*
