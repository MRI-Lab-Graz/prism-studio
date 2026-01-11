# Exercise 2: Creating & Editing JSON Metadata

**Time:** 25 minutes  
**Goal:** Add proper metadata to make your data self-documenting and reusable

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Understand JSON sidecar structure
- ✓ Fill in General, Technical, and item-level metadata
- ✓ Add value labels (Levels) for survey responses
- ✓ Use library templates to save time
- ✓ Validate that your metadata is complete

---

## Starting Point

**You'll use the dataset you created in Exercise 1:**
- Location: `../exercise_1_raw_to_bids/my_dataset/`
- Status: Structured correctly, but metadata is incomplete

**If you didn't complete Exercise 1:**
- A starter dataset is available in `starter_dataset/` (if instructor provided one)
- Or ask your instructor for help

---

## Your Task

Fill in the JSON sidecars with complete metadata so that anyone can understand:
- What survey was used (name, description)
- How it was administered (instructions, version)
- What each question means (item descriptions)
- What the response codes mean (value labels)

---

## Step-by-Step Instructions

### Step 1: Validate to See What's Missing

1. Open **PRISM Studio** (http://localhost:5001)
2. Go to **"Home"** or **"Validator"**
3. Click **"Select Dataset"**
4. Choose: `exercise_1_raw_to_bids/my_dataset/`
5. Click **"Validate Dataset"**

**You'll see warnings like:**
- ⚠️ Missing required field: `General.Name`
- ⚠️ Missing field: `General.Description`
- ℹ️ Recommended: Add `Technical.Language`

This is expected! The converter created basic sidecars, but we need to enrich them.

---

### Step 2: Open the JSON Editor

**From validation results:**
1. Find a survey file in the results: `sub-01_ses-01_task-phq9_survey.json`
2. Click the **"Edit"** button (✏️ pencil icon)

**Alternative path:**
1. Go to **"Library"** → **"Template Editor"**
2. Browse to your file
3. Click **"Edit Template"**

---

### Step 3: Fill in General Metadata

You should see a form or JSON editor. Fill in these fields:

#### General Section

**Name:**
```
Patient Health Questionnaire-9
```

**Description:**
```
9-item self-report questionnaire for depression screening and severity measurement. Assesses the presence and frequency of depressive symptoms over the past two weeks.
```

**Instructions:**
```
Participants rated how often they experienced each symptom over the past 2 weeks using a 4-point scale from "Not at all" to "Nearly every day".
```

**TermURL (optional):**
```
https://www.phqscreeners.com/
```

---

### Step 4: Add Technical Metadata

#### Technical Section

**Version:**
```
1.0
```

**Language:**
```
en
```
(Use "de" for German, "fr" for French, etc.)

**Format:**
```
survey
```

**LicenseType:**
```
open
```

---

### Step 5: Add Item-Level Metadata

This is the most important (and time-consuming) part!

For **each PHQ-9 item** (`phq9_1` through `phq9_9`), you need to add:
1. **Description** - The actual question text
2. **Levels** - What each response code means

#### Example: phq9_1

**Find the column metadata section** (might be called "Items" or "Columns")

**Add a new item or find `phq9_1`:**

**Description:**
```
Little interest or pleasure in doing things
```

**Levels:**
```json
{
  "0": "Not at all",
  "1": "Several days",
  "2": "More than half the days",
  "3": "Nearly every day"
}
```

**In the GUI:**
- If there's a form interface:
  - Description field: paste the question text
  - Levels: Click "Add Level" for each code
    - Code: `0` → Label: `Not at all`
    - Code: `1` → Label: `Several days`
    - Code: `2` → Label: `More than half the days`
    - Code: `3` → Label: `Nearly every day`

#### Complete Item List (PHQ-9)

<details>
<summary>📋 Click to see all 9 items</summary>

**phq9_1:**
- Description: `Little interest or pleasure in doing things`
- Levels: [same as above]

**phq9_2:**
- Description: `Feeling down, depressed, or hopeless`
- Levels: [same as above]

**phq9_3:**
- Description: `Trouble falling or staying asleep, or sleeping too much`
- Levels: [same as above]

**phq9_4:**
- Description: `Feeling tired or having little energy`
- Levels: [same as above]

**phq9_5:**
- Description: `Poor appetite or overeating`
- Levels: [same as above]

**phq9_6:**
- Description: `Feeling bad about yourself - or that you are a failure or have let yourself or your family down`
- Levels: [same as above]

**phq9_7:**
- Description: `Trouble concentrating on things, such as reading the newspaper or watching television`
- Levels: [same as above]

**phq9_8:**
- Description: `Moving or speaking so slowly that other people could have noticed. Or the opposite - being so fidgety or restless that you have been moving around a lot more than usual`
- Levels: [same as above]

**phq9_9:**
- Description: `Thoughts that you would be better off dead, or of hurting yourself in some way`
- Levels: [same as above]

</details>

---

### Step 6: Save Your Changes

1. Click **"Save"** button
2. Confirm the save was successful

**Important:** The changes you made to one file only affect that one subject's sidecar!

---

### Step 7: Copy to All Subjects (Time-Saver!)

Since all subjects answered the same questionnaire, the metadata should be identical across all JSON sidecars.

**Option A: Copy-paste** (manual but reliable)
1. Open the JSON file you just edited in a text editor
2. Copy the entire content
3. Paste into all other `*_task-phq9_survey.json` files
4. Save all files

**Option B: Use the GUI's "Apply to All"** (if available)
1. After editing one file, look for **"Apply to all similar files"** button
2. Click it
3. System copies the metadata to all matching files

---

### Step 8: Validate Again

1. Go back to **"Validator"**
2. Click **"Re-validate"** (or select the dataset again)
3. Check the results

**Expected:**
- ✅ All metadata warnings should be resolved
- ✅ Dataset should pass validation
- 🎉 Green light = success!

**If you still see warnings:**
- Double-check that all required fields are filled
- Check for JSON syntax errors (missing commas, quotes)
- Ask your instructor for help

---

## Time-Saving Tip: Use the Template!

Instead of typing all metadata manually, you can use the pre-made PHQ-9 template.

### Workshop Template Location:

The complete PHQ-9 template is provided at:
```
../library/survey/survey-phq9.json
```

### How to Use It:

**Option 1: Manual Copy (Recommended for Learning)**
1. Open `../library/survey/survey-phq9.json` in a text editor
2. Review the structure - see how it's organized
3. Copy relevant sections (General, Technical, item descriptions)
4. Paste into your own JSON files
5. Modify if needed for your specific implementation

**Option 2: Direct Copy**
```bash
# Copy the template to your first subject
cp ../library/survey/survey-phq9.json \
   ../exercise_1_raw_to_bids/my_dataset/sub-01/ses-01/survey/sub-01_ses-01_task-phq9_survey.json
```

**Option 3: GUI Library (if available)**
1. Go to **"Library"** in PRISM Studio
2. Look for **"PHQ-9"** in the survey templates
3. Click **"View"** or **"Preview"**
4. Click **"Copy to Clipboard"** or **"Use as Template"**
5. Paste into your JSON editor

**Template Contents:**
- Complete `General` section (Name, Description, Instructions)
- Complete `Technical` section (Version, Language, Format)
- All 9 items with full descriptions and value labels
- Multiple languages (English and German)

**After using the template:**
- Review to ensure it matches your data
- Adjust any study-specific details
- Copy to all other subject files

---

## Understanding JSON Structure

Your completed JSON file should look like this:

```json
{
  "General": {
    "Name": "Patient Health Questionnaire-9",
    "Description": "9-item self-report questionnaire...",
    "Instructions": "Participants rated..."
  },
  "Technical": {
    "Version": "1.0",
    "Language": "en",
    "Format": "survey"
  },
  "phq9_1": {
    "Description": "Little interest or pleasure in doing things",
    "Levels": {
      "0": "Not at all",
      "1": "Several days",
      "2": "More than half the days",
      "3": "Nearly every day"
    }
  },
  "phq9_2": {
    "Description": "Feeling down, depressed...",
    "Levels": { ... }
  }
  ... (all 9 items)
}
```

**Key structure:**
- **General** = Survey-level information
- **Technical** = Implementation details
- **Item keys** = Column/variable names from your TSV file
- **Levels** = Value labels (code → meaning)

---

## Why Is This Important?

### Without Metadata:
```
phq9_1: 2
```
What does this mean? 🤷

### With Metadata:
```
Question: "Little interest or pleasure in doing things"
Response: 2 = "More than half the days"
```
Now it's clear! 🎯

### Benefits:
1. **Self-documenting data** - Anyone can understand it without asking you
2. **Statistical software** - Value labels import into SPSS/R/Jamovi automatically
3. **Long-term archiving** - Your future self will thank you
4. **Data sharing** - Collaborators don't need a separate codebook
5. **Reproducibility** - Methods are documented in machine-readable format

---

## Checkpoint: Did It Work?

✅ **You should have:**
- [ ] All JSON sidecars with complete `General` section
- [ ] All JSON sidecars with complete `Technical` section
- [ ] All 9 PHQ-9 items with `Description` and `Levels`
- [ ] No validation warnings about missing metadata
- [ ] Green checkmark from validator ✓

---

## Troubleshooting

### Problem: "JSON syntax error"
**Solution:** 
- Check for missing commas between items
- Check for missing quotes around strings
- Use a JSON validator tool to find the error

### Problem: "Cannot save file"
**Solution:**
- Check file permissions
- Make sure the file isn't open in another program
- Try saving to a different location first, then copy back

### Problem: "Validation still shows warnings"
**Solution:**
- Make sure you saved the file
- Check that you edited the right file (in the dataset, not in raw_data/)
- Click "Re-validate" to refresh results

---

## Next Steps

✅ **Excellent work!** Your dataset is now:
- ✓ Properly structured (Exercise 1)
- ✓ Fully documented (Exercise 2)

**In Exercise 3**, you'll learn how to:
- Calculate total scores automatically
- Export to SPSS with all metadata preserved
- Generate analysis-ready outputs

---

## Bonus Challenge (If You Have Extra Time)

1. **Add more metadata:**
   - `General.Authors`: Your name
   - `General.URL`: Link to official PHQ-9 documentation
   - `General.Citation`: Full reference for the questionnaire

2. **Edit participants.json:**
   - Add descriptions for demographic columns
   - Add value labels for categorical variables (e.g., gender, education)

3. **Create a template:**
   - Save your PHQ-9 metadata to the library
   - Try applying it to a new dataset

---

**Ready for Exercise 3?** → Go to `../exercise_3_recipes_export/`
