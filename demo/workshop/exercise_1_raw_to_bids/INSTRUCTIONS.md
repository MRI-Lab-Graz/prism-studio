# Exercise 1: Converting Raw Data to BIDS Structure

**Time:** 30 minutes  
**Goal:** Transform unstructured CSV files into a valid BIDS/PRISM dataset

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Understand BIDS folder hierarchy (Dataset → Subject → Session → Modality)
- ✓ Know BIDS file naming conventions
- ✓ Use the GUI converter to create structured datasets
- ✓ Recognize the importance of sidecar JSON files

---

## Starting Materials

Look in the `raw_data/` folder:
- **`participants_raw.tsv`** - Demographic information about your participants
- **`phq9_scores.tsv`** - PHQ-9 depression questionnaire responses (tab-delimited file with columns `phq9_01` through `phq9_09` that already match the metadata template)

These are typical "raw" data files - just tab-delimited exports from your data collection tool.

---

## Your Task

Convert the PHQ-9 data into a proper BIDS/PRISM dataset with the correct folder structure and file naming.

---

## Step-by-Step Instructions

### Step 1: Launch PRISM Studio
1. Open your web browser
2. Go to: **http://localhost:5001**
3. You should see the PRISM Studio home page

### Step 2: Open the Converter Tool
1. Click on **"Converter"** in the navigation menu (top or sidebar)
2. Select **"Survey Data Converter"** or **"Raw Data to BIDS"**

### Step 3: Load Your Data
1. Click **"Browse"** or **"Choose File"**
2. Navigate to: `demo/workshop/exercise_1_raw_to_bids/raw_data/phq9_scores.tsv`
3. Click **"Upload"** or **"Load File"**
4. Preview your data - you should see columns and rows

### Step 4: Map Columns
The converter needs to know which column represents what:

**Participant ID:**
- Find the column with subject IDs (likely called `ID`, `SubjectID`, or `participant_id`)
- In the dropdown, select: **"This column represents → participant_id"**

**Session (if present):**
- If you have a `session` or `visit` column, map it to → `session`
- If not, the system will use `ses-01` for all participants

**Survey/Task Name:**
- Enter: **`phq9`**
- This will appear in your filenames as `task-phq9`

**Modality:**
- Select: **`survey`**

**Data Columns:**
- The remaining columns (`phq9_01`, `phq9_02`, ..., `phq9_09`) already match the survey template, so leave their names unchanged when converting
- Make sure column names don't have spaces or special characters

### Step 5: Configure Output
1. **Output Directory:**
   - Click **"Set Output Folder"**
   - Navigate to: `demo/workshop/exercise_1_raw_to_bids/`
   - Create a new folder called: **`my_dataset`**
   - Select this folder

2. **Preview Filename:**
   - Check the preview: `sub-{id}_ses-{session}_task-phq9_survey.tsv`
   - This should look correct!

3. **Options to Enable:**
   - ☑ **Generate sidecars** (JSON files)
   - ☑ **Create participants.tsv**
   - ☑ **Create dataset_description.json**

### Step 6: Convert!
1. Click **"Convert to BIDS"** or **"Generate Dataset"**
2. Wait for the progress bar
3. Success message should appear: "✓ Created X files"

### Step 7: Explore Your Dataset
Navigate to `my_dataset/` and explore the structure:

```
my_dataset/
├── dataset_description.json      ← Describes your dataset
├── participants.tsv               ← One row per participant
└── sub-01/                        ← One folder per subject
    └── ses-01/                    ← One folder per session
        └── survey/                ← Modality folder
            ├── sub-01_ses-01_task-phq9_survey.tsv    ← Data file
            └── sub-01_ses-01_task-phq9_survey.json   ← Metadata (sidecar)
```

**Open some files and look inside!**

---

## Checkpoint: Did It Work?

✅ **You should have:**
- [ ] A `my_dataset/` folder with proper structure
- [ ] `dataset_description.json` at the root
- [ ] `participants.tsv` at the root
- [ ] Folders named `sub-01/`, `sub-02/`, `sub-03/`, etc.
- [ ] Inside each: `ses-01/survey/`
- [ ] `.tsv` data files with proper BIDS naming
- [ ] `.json` sidecar files (one for each `.tsv`)

✅ **File naming should follow this pattern:**
- `sub-01` (with hyphen, not `sub01`)
- `ses-01` (with hyphen, not `ses01`)
- `task-phq9` (with hyphen, not `taskphq9`)
- Underscores `_` separate the entities
- Example: `sub-01_ses-01_task-phq9_survey.tsv`

---

## Quick Validation Test

Let's check if your dataset is valid:

1. Go to **"Home"** or **"Validator"** in PRISM Studio
2. Click **"Select Dataset"**
3. Choose your `my_dataset/` folder
4. Click **"Validate Dataset"**

**Expected Result:**
- ⚠️ Warnings about missing metadata (this is OK! We'll fix this in Exercise 2)
- ✓ No critical errors about file structure or naming
- ✓ All files detected correctly

**If you see errors about file naming or structure:**
- Double-check the filename pattern
- Make sure there are hyphens after `sub-`, `ses-`, `task-`
- Ask your instructor for help!

---

## What Just Happened?

🎯 **You converted unstructured data into a standardized format!**

**Before:** Just a CSV file sitting somewhere on your computer
**After:** A properly structured dataset that:
- Follows international standards (BIDS)
- Can be understood by automated tools
- Has a clear hierarchy (subject → session → modality)
- Includes metadata files (JSON sidecars)
- Is ready for sharing and archiving

---

## Key Concepts

### BIDS Hierarchy
```
Dataset (study level)
└── Subject (participant level) - sub-01, sub-02, ...
    └── Session (visit level) - ses-01, ses-02, ...
        └── Modality (data type) - survey, eeg, physio, ...
            └── Files (actual data)
```

### File Naming Rules
- **Entities** are key-value pairs: `sub-01`, `ses-01`, `task-phq9`
- **Separator** between entities: underscore `_`
- **Separator** within entities: hyphen `-`
- **Suffix** describes the modality: `survey`, `eeg`, `physio`
- **Extension** is the file type: `.tsv`, `.json`, `.nii.gz`

### Sidecar Files
- Every data file (`.tsv`, `.nii.gz`, etc.) should have a `.json` sidecar
- The sidecar contains metadata about the data file
- Same filename, just different extension
- Example:
  - Data: `sub-01_ses-01_task-phq9_survey.tsv`
  - Sidecar: `sub-01_ses-01_task-phq9_survey.json`

---

## Troubleshooting

### Problem: "Invalid column mapping"
**Solution:** Make sure you selected a column for participant_id

### Problem: "Invalid characters in filename"
**Solution:** Check that task name doesn't have spaces or special characters

### Problem: "Output folder not found"
**Solution:** Make sure you created the `my_dataset/` folder first

### Problem: "No data rows found"
**Solution:** Check that your CSV has data (not just headers)

---

## Next Steps

✅ **Congratulations!** Your data is now structured.

But wait - the JSON sidecars are mostly empty! They only have basic information.

**In Exercise 2**, you'll learn how to fill in the metadata to make your dataset truly self-documenting.

---

## Bonus Challenge (If You Have Extra Time)

1. **Try with participants data:**
   - Load `participants_raw.tsv`
   - See if you can update the main `participants.tsv` file

2. **Add a second survey:**
   - If there's a `gad7_anxiety.csv` file, convert it too
   - It should go into the same dataset structure
   - Files will be named: `sub-01_ses-01_task-gad7_survey.tsv`

3. **Explore the converter settings:**
   - Can you change the file suffix from `survey` to `beh`?
   - What happens if you choose a different modality?

---

**Ready for Exercise 2?** → Go to `../exercise_2_json_metadata/`
