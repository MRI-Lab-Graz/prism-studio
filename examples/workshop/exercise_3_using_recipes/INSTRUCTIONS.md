# Exercise 3: Using Recipes

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

**You'll use the dataset you completed in Exercise 1:**
- Location: `../exercise_1_raw_data/my_dataset/`
- Status: Properly structured.

**Requirements:**
- Your dataset must be valid.
- JSON sidecars should ideally have metadata, but the recipe can work with raw columns too.

---

## What Are Recipes?

**Recipes** are JSON files that define scoring logic:
- Which items to sum/average
- How to reverse-code items (if needed)
- How to calculate subscales
- Clinical cutoffs for interpretation

---

## Your Task

Apply the Wellbeing and Fitness recipes to your dataset to:
1. Calculate the wellbeing total score (sum of 5 items)
2. Calculate the fitness composite if you converted the biometrics data
3. Export results to SPSS format

---

## Step-by-Step Instructions

### Step 1: Verify Recipe File Exists

The recipes are located at `demo/workshop/recipes/surveys/wellbeing.json` and `demo/workshop/recipes/biometrics/fitness.json`.

---

### Step 2: Open Recipes & Scoring Tool

1. Open **PRISM Studio** (http://localhost:5001)
2. Click **"Recipes & Scoring"** in the navigation menu

---

### Step 3: Select Your Dataset

**Dataset Folder:**
1. Click **"Browse"** button next to "PRISM Dataset Folder"
2. Navigate to: `demo/workshop/exercise_1_raw_data/my_dataset/`
3. Select this folder

---

### Step 4: Configure Recipe Settings

#### For Wellbeing Survey:
- **Modality:** Select `Survey`
- **Recipe:** Select `wellbeing`
- **Output Format:** Select `SPSS (.sav)` or `Excel (.xlsx)`
- Click **"Run Scoring & Export"**

#### For Fitness Data (Bonus):
- **Modality:** Select `Biometrics`
- **Recipe:** Select `fitness`
- Click **"Run Scoring & Export"**

---

### Step 5: Verify Results

Check your output folder (usually the same as the dataset or a `derivatives/` subfolder):
- You should see `wellbeing_scores.sav` (or `.xlsx`)
- Open it and check the new columns (e.g., `wellbeing_total`)
- Notice that the variable labels and value labels are preserved!

---

## What Just Happened?

🎯 **You went from raw data to analysis-ready results in minutes!**

Instead of manual summing in Excel, you used a **machine-readable recipe** that:
- Summarized your data automatically
- Preserved all your hard-earned metadata
- Created a format ready for statistical software
- Documented exactly how the scores were calculated

---

**Next Steps:**
Now that you've processed your data, let's learn how to create your own survey templates from scratch!

**Ready for Exercise 4?** → Go to `../exercise_4_templates/`
