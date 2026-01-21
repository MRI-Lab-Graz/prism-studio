# PRISM Workshop Handout: Wellbeing Survey Analysis

Welcome to the PRISM Hands-on Workshop! This guide will walk you through analyzing wellbeing survey data using PRISM Studio.

**Workshop Goals:**
- ✅ Set up an organized research project (YODA principles)
- ✅ Convert raw Excel survey data to BIDS/PRISM format
- ✅ Add proper metadata for documentation and sharing
- ✅ Calculate scores and export to SPSS

**Example Dataset:** WHO-5 Well-Being Index  
**Duration:** ~90 minutes  
**Method:** Graphical interface (no command line!)

---

## Overview of Exercises

| # | Exercise | Duration | What You'll Do |
|---|----------|----------|----------------|
| **0** | Project Setup | 15 min | Create YODA-structured project |
| **1** | Data Conversion | 30 min | Excel → PRISM format |
| **2** | Metadata & Validation | 25 min | Add item descriptions and validate |
| **3** | Scoring & Export | 20 min | Calculate scores → SPSS file |

---

## Getting Started

### Launch PRISM Studio

**Windows (standalone executable):**
- Double-click `PrismValidator.exe`
- Browser opens to **http://localhost:5001**

**From source:**
```powershell
# Windows
.\.venv\Scripts\Activate.ps1
python prism-studio.py
```

```bash
# macOS/Linux
source .venv/bin/activate
python prism-studio.py
```

### Workshop Materials

Located in `examples/workshop/`:
- `exercise_0_project_setup/` - Instructions for YODA setup
- `exercise_1_raw_data/raw_data/wellbeing.xlsx` - Raw survey data
- `exercise_3_using_recipes/recipe-wellbeing.json` - Scoring recipe
- `exercise_4_templates/survey-wellbeing.json` - Metadata template

---

## Exercise 0: Project Setup with YODA

**⏱ Time:** 15 minutes  
**🎯 Goal:** Create an organized, reproducible research project

### Why YODA?

YODA (Yet anOther Data Analysis) separates:
- **sourcedata/** - Original files (preserved, never edited)
- **rawdata/** - Standardized PRISM format
- **code/** - Analysis scripts
- **derivatives/** - Results and exports

This structure enables version control, reproducibility, and collaboration.

### Steps

1. **Navigate to Projects**
   - Click **Projects** in sidebar
   - URL: http://localhost:5001/projects

2. **Create New Project**
   - Project Name: `Wellbeing_Study_Workshop`
   - Location: Choose your preferred folder (Desktop, Documents, etc.)
   - Template: **YODA Structure** (if option exists)
   - Click **Create & Activate**

3. **Verify Structure**
   Your project should have:
   ```
   Wellbeing_Study_Workshop/
   ├── sourcedata/
   ├── rawdata/
   ├── code/
   ├── derivatives/
   └── README.md
   ```

4. **Confirm Active**
   - Top of screen shows: "Active Project: Wellbeing_Study_Workshop"

✅ **Complete!** You have a professional research project structure.

---

## Exercise 1: Converting Raw Survey Data

**⏱ Time:** 30 minutes  
**🎯 Goal:** Transform `wellbeing.xlsx` into BIDS/PRISM format

### Understanding the Raw Data

Open `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx` to see:

| Column | Description |
|--------|-------------|
| `participant_id` | DEMO001, DEMO002, ... |
| `session` | baseline, followup, ... |
| `age`, `sex`, `education`, `handedness` | Demographics |
| `WB01` - `WB05` | WHO-5 survey items (0-5 scale) |
| `completion_date` | When survey was taken |

**WHO-5 Items:**
- WB01: "I have felt cheerful and in good spirits"
- WB02: "I have felt calm and relaxed"
- WB03: "I have felt active and vigorous"
- WB04: "I woke up feeling fresh and rested"
- WB05: "My daily life has been filled with things that interest me"

### Conversion Steps

#### 1. Open Survey Converter
- Click **Converter** in navigation
- Select **"Survey Data Converter"** or **"Raw Data to BIDS"**

#### 2. Upload File
- Click **Browse** or **Choose File**
- Navigate to `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`
- Click **Upload**
- Preview should show your data

#### 3. Map Columns

**Identity Mapping:**
- **Participant ID** → Select `participant_id` column
- **Session** → Select `session` column
  - *(System will format as sub-DEMO001, ses-baseline)*

**Survey Settings:**
- **Task Name:** `wellbeing`
  - *(Used in filenames: `task-wellbeing`)*
- **Modality:** `survey`
- **Suffix:** `survey`

**Data Columns:**
- Survey items (`WB01`-`WB05`) automatically included
- Demographics can be added to `participants.tsv`

#### 4. Configure Output
- **Output Directory:** 
  - Click **Set Output Folder**
  - Navigate to your project's `rawdata/` folder
  - `Wellbeing_Study_Workshop/rawdata/`

- **Options to Enable:**
  - ✅ Generate JSON sidecars
  - ✅ Create participants.tsv
  - ✅ Create dataset_description.json

#### 5. Convert
- Click **Convert to BIDS** or **Generate**
- Wait for progress bar
- Success message shows number of files created

#### 6. Review Structure

Navigate to `Wellbeing_Study_Workshop/rawdata/`:
```
rawdata/
├── dataset_description.json
├── participants.tsv
├── sub-DEMO001/
│   └── ses-baseline/
│       └── survey/
│           ├── sub-DEMO001_ses-baseline_task-wellbeing_survey.tsv
│           └── sub-DEMO001_ses-baseline_task-wellbeing_survey.json
├── sub-DEMO002/
│   └── ses-baseline/
│       └── survey/
│           ├── sub-DEMO002_ses-baseline_task-wellbeing_survey.tsv
│           └── sub-DEMO002_ses-baseline_task-wellbeing_survey.json
...
```

**Key Points:**
- Every data file (`.tsv`) has a metadata sidecar (`.json`)
- Filenames follow BIDS convention: `sub-<ID>_ses-<SESSION>_task-<NAME>_<SUFFIX>.<EXT>`
- Folder hierarchy: Dataset → Subject → Session → Modality

✅ **Complete!** Your data is now in PRISM format.

---

## Exercise 2: Adding Metadata & Validation

**⏱ Time:** 25 minutes  
**🎯 Goal:** Document your survey and validate the dataset

### Why Metadata Matters

JSON sidecars make your data:
- **Self-documenting** - Anyone can understand what was measured
- **Reusable** - Others can reanalyze your data
- **Citable** - Proper attribution to original survey authors
- **Machine-readable** - Tools can automatically process it

### Steps

#### 1. Run Validation
- Go to **Validator** or **Home**
- Click **Select Dataset**
- Choose `Wellbeing_Study_Workshop/rawdata/`
- Click **Validate Dataset**

**Expected errors:**
- Missing survey metadata (name, authors, citation)
- Missing item descriptions
- Missing response level labels

#### 2. Copy Template to Your Project

The wellbeing survey template already exists. Copy it:
- **From:** `examples/workshop/exercise_4_templates/survey-wellbeing.json`
- **To:** Your project's library folder (PRISM Studio may have a "Library" section)

Or use the Template Editor in PRISM Studio:
- Go to **Tools** → **Template Editor**
- Browse to `examples/workshop/exercise_4_templates/survey-wellbeing.json`
- Click **Load Template**

#### 3. Edit a Sidecar

Open any survey sidecar JSON file:
`rawdata/sub-DEMO001/ses-baseline/survey/sub-DEMO001_ses-baseline_task-wellbeing_survey.json`

**Using PRISM Studio:**
- Click **Edit** next to the file in validation results
- Or use **Tools** → **JSON Editor**

**Manual editing:**
- Open in text editor (VS Code, Notepad++, etc.)

#### 4. Add Required Metadata

Merge content from `survey-wellbeing.json` into your sidecar:

```json
{
  "Study": {
    "OriginalName": {
      "en": "Wellbeing Survey (WHO-5 adapted)"
    },
    "Abbreviation": "WB",
    "Authors": ["Topp", "C.W.", "Østergaard", "S.D.", "Søndergaard", "S.", "Bech", "P."],
    "Year": 2015,
    "DOI": "10.1159/000376585",
    "NumberOfItems": 5,
    "Instructions": {
      "en": "Please indicate for each of the five statements which is closest to how you have been feeling over the last two weeks."
    }
  },
  "WB01": {
    "Description": {
      "en": "I have felt cheerful and in good spirits"
    },
    "Levels": {
      "5": {"en": "All of the time"},
      "4": {"en": "Most of the time"},
      "3": {"en": "More than half the time"},
      "2": {"en": "Less than half the time"},
      "1": {"en": "Some of the time"},
      "0": {"en": "At no time"}
    }
  },
  ... (repeat for WB02-WB05)
}
```

**Tip:** Copy the entire template content - it's faster than typing!

#### 5. Validate Again
- Run validator again
- Check that errors are resolved
- All survey files should now pass validation

✅ **Complete!** Your dataset is now fully documented and valid.

---

## Exercise 3: Calculating Scores & Exporting

**⏱ Time:** 20 minutes  
**🎯 Goal:** Calculate wellbeing total scores and export to SPSS

### Understanding Recipes

Recipes are instructions for:
- Calculating total/subscale scores
- Handling reverse-scored items
- Computing derived variables
- Applying quality checks

### Steps

#### 1. Copy Recipe to Your Project

- **Source:** `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json`
- **Destination:** Create a `recipes/` folder in your project:
  ```
  Wellbeing_Study_Workshop/
  └── recipes/
      └── survey/
          └── recipe-wellbeing.json
  ```

Or use PRISM Studio:
- Go to **Recipes** or **Tools** → **Recipes**
- Click **Import Recipe**
- Browse to `recipe-wellbeing.json`

#### 2. Review Recipe Content

The recipe specifies:
```json
{
  "Survey": {
    "Name": "Wellbeing"
  },
  "Scores": {
    "Total": {
      "Items": ["WB01", "WB02", "WB03", "WB04", "WB05"],
      "Method": "sum",
      "Range": {"min": 5, "max": 35}
    }
  }
}
```

**This means:** Sum all 5 items to get total score (5-35 range)

#### 3. Run Recipe

In PRISM Studio:
- Go to **Recipes & Scoring**
- Select your dataset: `rawdata/`
- Select recipe: `recipe-wellbeing`
- Click **Run Recipe**

#### 4. Configure Export

**Format Options:**
- **SPSS (.sav)** - Recommended! Includes value labels
- **Excel (.xlsx)** - Good for quick viewing
- **CSV (.csv)** - Plain text, universal

**Layout:**
- **Long format** - One row per session (sub-DEMO001, baseline)
- **Wide format** - One row per participant (multiple session columns)

**Select:** SPSS (.sav), Long format

#### 5. Export Results

- Output location: `Wellbeing_Study_Workshop/derivatives/`
- Filename: `wellbeing_scores.sav`
- Click **Export**

#### 6. Verify in SPSS/Excel

Open the exported file:
```
derivatives/
└── wellbeing_scores.sav
```

**Expected columns:**
- `participant_id`
- `session`
- `WB01`, `WB02`, `WB03`, `WB04`, `WB05` (original items)
- `Total` (calculated score)
- Demographics (if included)

**In SPSS:**
- Variable labels are preserved
- Value labels show ("All of the time", "Most of the time", etc.)
- Ready for statistical analysis!

✅ **Complete!** You have analysis-ready data with calculated scores.

---

## Summary & Next Steps

### What You've Accomplished

1. ✅ Created a YODA-structured research project
2. ✅ Converted raw Excel data to BIDS/PRISM format
3. ✅ Added comprehensive metadata for reproducibility
4. ✅ Calculated wellbeing scores using a recipe
5. ✅ Exported analysis-ready data to SPSS

### Your Final Project Structure

```
Wellbeing_Study_Workshop/
├── sourcedata/
│   └── wellbeing.xlsx           # Original file (preserved)
├── rawdata/
│   ├── dataset_description.json
│   ├── participants.tsv
│   └── sub-*/ses-*/survey/       # PRISM-formatted data
├── code/                         # Your analysis scripts go here
├── derivatives/
│   └── wellbeing_scores.sav      # Calculated scores
└── recipes/
    └── survey/
        └── recipe-wellbeing.json
```

### Next Steps with Your Own Data

**To use PRISM with your research:**

1. **Survey Library**
   - Check `official/library/survey/` for existing surveys
   - Create custom templates for your instruments
   - Share templates with community!

2. **Recipes**
   - Browse `official/recipe/survey/` for scoring formulas
   - Adapt existing recipes or create new ones
   - Include subscales, reverse coding, cutoff scores

3. **Data Sharing**
   - PRISM datasets are BIDS-compatible
   - Can be uploaded to OpenNeuro, OSF, etc.
   - Metadata ensures others can understand your data

4. **Integration with Analysis**
   - Use BIDS Apps (fMRIPrep, etc.) if you have imaging data
   - Import SPSS files into R, Python, JASP, Jamovi
   - Metadata is preserved throughout pipeline

### Resources

- **Documentation:** https://psycho-validator.readthedocs.io/
- **Issues/Questions:** https://github.com/your-repo/prism-validator/issues
- **Survey Templates:** `official/library/survey/`
- **Example Recipes:** `official/recipe/survey/`

### Feedback

We'd love your feedback!
- What worked well?
- What was confusing?
- What features would help your research?

**Thank you for attending the PRISM workshop!** 🎉
