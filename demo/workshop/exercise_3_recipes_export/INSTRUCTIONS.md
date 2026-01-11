# Exercise 3: Recipes & SPSS Export

**Time:** 20 minutes  
**Goal:** Calculate total scores automatically and export analysis-ready data to SPSS

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Understand the recipe system for automated scoring
- ✓ Apply recipes to calculate total scores and subscales
- ✓ Export data to SPSS (.sav) with full metadata
- ✓ Generate codebooks and methods text automatically
- ✓ Open and verify the results in SPSS/Jamovi

---

## Starting Point

**You'll use the dataset you completed in Exercise 2:**
- Location: `../exercise_1_raw_to_bids/my_dataset/`
- Status: Properly structured AND fully documented with metadata

**Requirements:**
- Your dataset must be valid (passed validation in Exercise 2)
- JSON sidecars must have complete metadata (especially `Levels`)

---

## What Are Recipes?

**Recipes** are JSON files that define scoring logic:
- Which items to sum/average
- How to reverse-code items (if needed)
- How to calculate subscales
- Clinical cutoffs for interpretation

**Why recipes?**
- 🔄 **Reproducible** - Same logic every time
- 📝 **Documented** - Scoring method is written down
- 🤖 **Automated** - No manual Excel formulas
- 🔬 **Transparent** - Anyone can inspect the scoring logic

---

## Your Task

Apply the PHQ-9 recipe to your dataset to:
1. Calculate the total depression score (sum of 9 items)
2. Export results to SPSS format
3. Verify that variable labels and value labels are preserved

---

## Step-by-Step Instructions

### Step 1: Verify Recipe File Exists

The PHQ-9 recipe is already part of the workshop materials and lives at `demo/workshop/recipes/surveys/phq9.json`.

Open that file in your editor to confirm:
- `Survey.Name` is "Patient Health Questionnaire-9"
- `Scores[0].Items` lists `phq9_01` through `phq9_09`
- `Method` is `sum` and `Range` is `0-27`

If PRISM does not list "phq9" in the recipes dropdown, make sure your workspace root contains `demo/workshop/recipes/surveys/phq9.json` (create the folders if needed and copy the file from the repository root).

---

### Step 2: Open Recipes & Scoring Tool

1. Open **PRISM Studio** (http://localhost:5001)
2. Click **"Recipes & Scoring"** in the navigation menu
3. You'll see the scoring interface

---

### Step 3: Select Your Dataset

**Dataset Folder:**
1. Click **"Browse"** button next to "PRISM Dataset Folder"
2. Navigate to: `demo/workshop/exercise_1_raw_to_bids/my_dataset/`
3. Select this folder

**Verification:**
- System will check if it's a valid PRISM dataset
- Should show ✓ "Valid BIDS structure detected"
- If error: Make sure you selected the root folder (contains `dataset_description.json`)

---

### Step 4: Configure Recipe Settings

Fill in the recipe configuration form:

#### Modality
- Select: **`Survey`**
- (This tells the system to look in `recipes/surveys/`)

#### Recipe Filter
- Enter: **`phq9`**
- (This will match `recipes/surveys/phq9.json`)
- Leave empty to run all available recipes

#### Output Format
- Select: **`SPSS (.sav - contains Levels/Labels)`** ⭐
- This is the key format for preserving metadata!

#### Layout
- Select: **`Long (one row per session)`**
- (Alternative: `Wide` is useful for repeated measures - one row per participant)

#### Language
- Select: **`English`**
- (This affects variable labels in the output)

#### Additional Options
- ☐ **Include Raw Data Columns** - Uncheck (we only want calculated scores)
- ☑ **Generate Codebook** - Keep checked (creates documentation)

---

### Step 5: Run the Recipe!

1. Click **"Run Scoring"** or **"Process Dataset"**
2. Watch the progress indicator:
   - 📊 Processing recipe: phq9
   - 📝 Reading survey files... (found X files)
   - 🧮 Calculating scores...
   - 💾 Writing outputs...
3. Wait for success message

**Expected message:**
```
✓ Processing complete
  - Processed: 15 files
  - Generated: 1 output file
  - Format: SPSS (.sav)
  - Location: recipes/surveys/phq9/
```

---

### Step 6: Review the Outputs

The system created several files in your dataset:

```
my_dataset/
└── recipes/
    └── surveys/
        ├── dataset_description.json          ← Describes the derivative
        └── phq9/
            ├── phq9.sav                      ← ⭐ SPSS data file
            ├── phq9_codebook.json            ← Machine-readable metadata
            ├── phq9_codebook.tsv             ← Human-readable codebook
            └── methods_boilerplate.md        ← Auto-generated methods text
```

**In the GUI:**
- Click **"View Results"** or **"Download"**
- You'll see a preview table

**Expected data:**
| participant_id | session | phq9_total |
|----------------|---------|------------|
| sub-01         | ses-01  | 5          |
| sub-02         | ses-01  | 19         |
| sub-03         | ses-01  | 1          |
| ...            | ...     | ...        |

---

### Step 7: Download and Inspect the SPSS File

1. **Download the file:**
   - Click **"Download SPSS File"**
   - Or navigate to: `recipes/surveys/phq9/phq9.sav`
   - Copy to your desktop for easy access

2. **Open in SPSS (or Jamovi/PSPP):**
   - Launch SPSS
   - File → Open → Data
   - Select `phq9.sav`

3. **Check the Variable View:**
   - Switch to "Variable View" tab
   - You should see:

| Name          | Label                              | Values     |
|---------------|-------------------------------------|-----------|
| participant_id| Participant identifier             | None      |
| session       | Session identifier                  | None      |
| phq9_total    | Total depression severity score     | See below |

4. **Check Value Labels:**
   - Click on `phq9_total` → Values column
   - You should see interpretation categories (if defined in recipe):
     - 1 = "Minimal depression (0-4)"
     - 2 = "Mild depression (5-9)"
     - 3 = "Moderate depression (10-14)"
     - 4 = "Moderately severe depression (15-19)"
     - 5 = "Severe depression (20-27)"

5. **Switch to Data View:**
   - See the actual scores
   - All ready for analysis!

---

### Step 8: Try Running Statistics!

Now that the data is in SPSS, you can immediately analyze it:

**Example: Descriptive Statistics**
```
DESCRIPTIVES VARIABLES=phq9_total
  /STATISTICS=MEAN STDDEV MIN MAX.
```

**Example: Frequency Table**
```
FREQUENCIES VARIABLES=phq9_total.
```

**No need to:**
- ❌ Manually calculate scores
- ❌ Define value labels
- ❌ Create a separate codebook
- ❌ Copy-paste variable labels

**Everything is already there!** ✨

---

### Step 9: Review the Methods Boilerplate

1. Navigate to: `recipes/surveys/methods_boilerplate.md`
2. Open the file (text editor or preview)

**You'll see auto-generated text like:**

> ## Data Standardization and Validation
> 
> Data were organized and validated according to the PRISM (Psychological Research Information System & Metadata) standard, which extends the Brain Imaging Data Structure (BIDS) to psychological research. Data processing and score calculation were performed automatically using the PRISM system, applying the scoring logic defined in machine-readable JSON recipes.
>
> ## Psychological Assessments
>
> ### Patient Health Questionnaire-9
> 9-item self-report questionnaire for depression screening and severity measurement. The instrument is based on Kroenke et al. (2001).
>
> **Scoring:**
> - `phq9_total`: sum score (9 items).

**You can copy this directly into your manuscript's Methods section!** 📄

---

### Step 10 (Optional): Try Excel Export

Want to see the data in Excel instead?

1. Go back to **"Recipes & Scoring"**
2. Change **Output Format** to: `Excel (.xlsx)`
3. Click **"Run Scoring"** again

**Excel output includes multiple sheets:**
- **Data** - The calculated scores
- **Codebook** - Variable descriptions and value labels
- **Survey Info** - Metadata from the recipe

**Great for:**
- Quick visual inspection
- Sharing with non-SPSS users
- Including in supplementary materials
- Presentations and reports

---

## What Just Happened?

🎯 **You automated the entire scoring workflow!**

### Traditional Workflow:
1. ❌ Open Excel
2. ❌ Write formula: `=SUM(B2:J2)`
3. ❌ Copy formula down for all participants
4. ❌ Hope you didn't make a mistake
5. ❌ Manually create codebook
6. ❌ Import to SPSS
7. ❌ Manually define variable labels
8. ❌ Manually define value labels
9. ❌ Write methods section by hand

### PRISM Workflow:
1. ✅ Click "Run Scoring"
2. ✅ Done! 🎉

### Benefits:
- **Reproducible** - Same recipe = same results every time
- **Documented** - Scoring logic is written down and version-controlled
- **Error-free** - No copy-paste mistakes
- **Time-saving** - Especially for large datasets or multiple instruments
- **Shareable** - Send the recipe file, anyone can reproduce your scores

---

## Understanding the Recipe File

Curious what's inside `recipes/surveys/phq9.json`?

**Basic structure:**
```json
{
  "RecipeVersion": "1.0",
  "Kind": "survey",
  "Survey": {
    "Name": "Patient Health Questionnaire-9",
    "TaskName": "phq9",
    "Description": "...",
    "Citation": "..."
  },
  "Transforms": {
    "Invert": {
      "Items": [],           ← Which items to reverse-code
      "Scale": {"min": 0, "max": 3}
    }
  },
  "Scores": [
    {
      "Name": "phq9_total",
      "Method": "sum",       ← How to calculate
      "Items": ["phq9_1", "phq9_2", ..., "phq9_9"],
      "Description": "...",
      "Range": {"min": 0, "max": 27},
      "Interpretation": {    ← Optional cutoffs
        "0-4": "Minimal depression",
        ...
      }
    }
  ]
}
```

**You can edit recipes or create new ones for your own instruments!**

---

## Checkpoint: Did It Work?

✅ **You should have:**
- [ ] A `recipes/surveys/phq9/` folder in your dataset
- [ ] `phq9.sav` file with data
- [ ] Codebook files (`.json` and `.tsv`)
- [ ] Methods boilerplate text
- [ ] SPSS file opens successfully
- [ ] Variable labels are present
- [ ] Value labels are present (if using interpretation categories)
- [ ] Data is ready for analysis

---

## Troubleshooting

### Problem: "Recipe not found: phq9"
**Solution:**
- Check that `recipes/surveys/phq9.json` exists
- Make sure the file name matches (case-sensitive!)
- Recipe filter must match the file name

### Problem: "No survey files found"
**Solution:**
- Make sure your dataset has `*_task-phq9_survey.tsv` files
- Check that the task name in your data matches the recipe

### Problem: "Column not found: phq9_1"
**Solution:**
- Recipe expects specific column names
- Check your TSV files - column headers must match
- If they're different (e.g., `PHQ9_1`), edit the recipe or re-convert your data

### Problem: SPSS file opens but no labels
**Solution:**
- Check that `pyreadstat` is installed
- Ensure your JSON sidecars have `Levels` defined
- Try re-running with "Generate Codebook" checked

### Problem: All scores are "n/a"
**Solution:**
- Check that column names match between TSV and recipe
- Look for missing data in source files
- Check recipe's `Missing` setting (ignore vs require_all)

---

## Congratulations! 🎉

You've completed all three exercises:

1. ✅ **Converted** raw data to BIDS structure
2. ✅ **Documented** your data with complete metadata
3. ✅ **Exported** analysis-ready outputs to SPSS

**Your dataset is now:**
- Structured according to international standards
- Fully documented and self-explaining
- Ready for analysis
- Ready for sharing and archiving
- Reproducible and transparent

---

## Next Steps

### Apply to Your Own Data
1. Try the workflow with your own research data
2. Start with a small pilot dataset (5-10 participants)
3. Build your library of templates for reuse

### Create Custom Recipes
1. Look at existing recipes for examples
2. Create recipes for your own instruments
3. Share them with the community!

### Advanced Features to Explore
- **Multiple sessions:** Longitudinal data with wide format
- **Subscales:** Calculate multiple scores from one instrument
- **Reverse coding:** Handle negatively-keyed items
- **Formulas:** Complex calculations (e.g., PSQI component scores)
- **NeuroBagel export:** Share data with brain imaging repositories

### Get Involved
- Report bugs on GitHub
- Contribute templates to the library
- Join the PRISM community
- Help improve the documentation

---

## Resources

### Documentation
- `docs/QUICK_START.md` - Getting started guide
- `docs/RECIPES.md` - Complete recipe documentation
- `docs/SPECIFICATIONS.md` - Technical details

### Support
- GitHub: [https://github.com/MRI-Lab-Graz/prism-studio](https://github.com/MRI-Lab-Graz/prism-studio)
- Email: (your instructor will provide)

### Example Files
- `library/survey/` - Survey templates
- `recipes/surveys/` - Scoring recipes
- `demo/workshop/reference_solution/` - Complete example dataset

---

**Thank you for participating in the PRISM workshop!**

We hope you found it useful. Please share your feedback with the instructor.

*Happy data standardizing!* 🎉
