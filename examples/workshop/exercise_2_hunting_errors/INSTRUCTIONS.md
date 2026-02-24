# Exercise 2: Hunt for Errors & Learn Data Validation

**⏱ Time:** 25 minutes  
**🎯 Goal:** Learn to identify and fix common data quality issues using PRISM Validator

**📚 Concepts:** Data validation, error detection, data quality, logging, troubleshooting

![Exercise 2 UI (Light Mode)](../../../docs/_static/screenshots/prism-studio-exercise-2-validation-light.png)

---

## What You'll Learn

By the end of this exercise, you will:
- ✅ Understand different types of validation messages (Error vs. Warning vs. Info)
- ✅ Identify common data quality issues (formatting, encoding, invalid values)
- ✅ Use PRISM Validator to detect problems
- ✅ Learn how to fix data problems before analysis
- ✅ Read and interpret validation reports

---

## Why Validation Matters

Imagine this scenario:
- You've collected data from 200 participants
- You start analyzing it two months later
- Halfway through, you discover participant #47 has an invalid age: "twenty-five" instead of "25"
- Or participant #103's sex is coded as "3" (undefined value)
- Or several files use commas instead of tabs

**Result:** Hours wasted debugging, potential errors in analysis, compromised results.

**Better approach:** Validate your data IMMEDIATELY after collection, before analysis.

PRISM Validator catches these issues automatically!

---

## The "Bad Examples" Folder

In the `bad_examples/` folder, you'll find 13 files with deliberate errors. These represent real-world problems that happen in actual research:

1. ❌ **Encoding issues** - File encoded as Latin-1, raw text expected UTF-8
2. ❌ **Delimiter issues** - File uses commas instead of tabs
3. ❌ **Missing data** - Columns are incomplete
4. ❌ **Duplicate IDs** - Same participant appears twice
5. ❌ **Invalid values** - Age is -5 or 999; sex is "M/F"; education is 10 (scale only goes 1-6)
6. ❌ **Missing columns** - Participant ID column is missing
7. ❌ **Wrong data types** - Date formatted as "2025-1-15" vs "2025-01-15"
8. ❌ **Empty files** - File exists but has no data
9. ❌ **Mismatched headers** - Column names don't match expected pattern
10. ❌ **Out-of-range values** - Survey response is "10" on a 0-5 scale
11. ❌ **Inconsistent formatting** - Some numbers have leading zeros, others don't
12. ❌ **Mixed delimiters** - Some rows use tabs, some use spaces
13. ❌ **Special character issues** - Participant IDs contain "@" or "!?

---

## Your Task: The Bug Hunt

Instead of following step-by-step instructions, you'll explore and investigate. This teaches you how to troubleshoot real data problems!

### **Step 1: Understand Your Workflow**

For each file you'll:
1. Look at the filename
2. Try to load it in PRISM
3. Observe what happens
4. Use the Validator to check for issues
5. Think about what's wrong and how to fix it

### **Step 2: Create a "Bad Dataset"**

First, you need to get these messy files into PRISM format so you can validate them.

1. **Open PRISM Studio:** http://localhost:5001
2. **Go to Converter:**
   - Click "Converter" → "Survey Data Converter"
   - Or navigate to: http://localhost:5001/converter

3. **Load the first bad file:**
   - Click "Browse"
   - Navigate to: `examples/workshop/exercise_2_hunting_errors/bad_examples/`
   - Select any `.tsv` file
   - Click "Load"

4. **What happens?**
   - Does it load successfully?
   - Does the preview work?
   - Does it show an error message?
   - What does the error message tell you?

5. **Try to convert:**
   - Even if there's an issue, try clicking "Convert"
   - Either it will work (file wasn't as bad as we thought!)
   - Or it will fail (this is what we're looking for!)

6. **Note the error message:**
   - Take a screenshot
   - Write down what it says
   - This is a clue!

### **Step 3: Use the Validator**

Once you've tried loading all the files, let's check them systematically.

1. **Go to Validator:**
   - In PRISM Studio: "Validator" or "Home"
   - Or: http://localhost:5001/validator

2. **Validate the bad_examples folder:**
   - Click "Select Dataset"
   - Navigate to: `examples/workshop/exercise_2_hunting_errors/bad_examples/`
   - Click "Validate"

3. **Read the validation report:**
   - What errors are listed?
   - How many warnings vs. errors?
   - What files are problematic?
   - Are there any info messages?

4. **Categorize the problems:**
   - Are they file format errors (encoding, delimiters)?
   - Are they data value errors (invalid ranges)?
   - Are they structural errors (missing columns)?
   - Are they missing metadata errors?

---

## Understanding Validation Messages

PRISM reports three types of messages:

### **🔴 ERROR** (Critical)
The file cannot be processed or data is invalid.

**Examples:**
- File encoding is not UTF-8
- Participant ID column is missing
- File has no data rows
- Date format is unparseable

**Action:** FIX IMMEDIATELY before proceeding

### **🟡 WARNING** (Important)
The file might work, but something is suspicious or incomplete.

**Examples:**
- Participant #47 appears twice
- Age value "-5" is physiologically impossible
- Survey response is "10" on a 0-5 scale
- Metadata is incomplete

**Action:** Investigate and fix these too!

### **ℹ️ INFO** (Helpful)
Just informational, usually not a problem.

**Examples:**
- Found 9 participants, 1 session, 10 variables
- File is UTF-8 encoded
- No reserved characters detected

**Action:** Good to know, but no action needed

---

## Investigation Sheet: Record Your Findings

As you investigate each problematic file, fill in this sheet:

| File Name | Loads? | Error Type | Problem Description | How to Fix It |
|-----------|--------|-----------|---------------------|---------------|
| bad_01... | Yes/No | Format/Data/Structure | e.g., "Comma-separated not tab-separated" | Use tab delimiter |
| bad_02... | Yes/No | ? | ? | ? |
| bad_03... | Yes/No | ? | ? | ? |
| ... | ... | ... | ... | ... |

---

## Guided Investigation: Find These Specific Errors

Try to locate files with these specific problems:

### **Challenge 1: Encoding Error**
Find a file that won't load because it's encoded in the wrong format.
- **Hint:** Look for file with special characters that don't display properly
- **Fix:** Save as UTF-8 encoding
- **Look for:** Error message about "encoding" or "character"

### **Challenge 2: Delimiter Error**
Find a file that uses commas instead of tabs.
- **Hint:** Filename might contain "csv" or "comma"
- **Fix:** Change delimiter from "," to "\t" (tab)
- **Look for:** Error about "column mismatch" or the preview looks weird

### **Challenge 3: Data Value Error**
Find a file where a participant has an impossible age (negative, 999, "unknown", etc.).
- **Hint:** Look for warnings about out-of-range values
- **Fix:** Replace with valid value or mark as missing
- **Look for:** Warning message: "Value X out of valid range for column age"

### **Challenge 4: Duplicate ID Error**
Find a file where one participant appears twice.
- **Hint:** The same participant_id appears in multiple rows
- **Fix:** Remove duplicate row or merge data
- **Look for:** Warning: "Duplicate participant ID"

### **Challenge 5: Empty File Error**
Find a file that exists but has no data.
- **Hint:** Very small file size or minimal filename
- **Fix:** Either add data or remove the file
- **Look for:** Error: "No data rows to process"

### **Challenge 6: Missing Column Error**
Find a file missing a required column (like participant_id).
- **Hint:** Converter fails immediately when loading
- **Fix:** Add the missing column
- **Look for:** Error: "Missing required column: participant_id"

---

## Tips for Successful Hunting

1. **Read error messages carefully** - They usually tell you exactly what's wrong!
2. **Check file size** - Empty files are tiny (< 100 bytes)
3. **Open in text editor** - Manually inspect first few lines to spot delimiter issues
4. **Look at file extensions** - .csv vs .tsv vs .txt might hint at the problem
5. **Check column headers** - Make sure they match expected names exactly
6. **Look at data values** - Do the numbers make sense? (Age 250? Sex "3"?)
7. **Use the Validator** - It will find many issues automatically!

---

## Bonus Challenges (If You Have Time)

1. **Try to FIX a bad file:**
   - Take one of the problematic files
   - Open in a text editor or spreadsheet program
   - Fix the error (change delimiter, fix encoding, etc.)
   - Save with a new name
   - Try to convert it again
   - Success = you've fixed real data!

2. **Create your own bad file:**
   - Start with `wellbeing.tsv`
   - Intentionally introduce an error (wrong age, duplicate participant, etc.)
   - Challenge a classmate to find the error using Validator!

3. **Compare multiple validators:**
   - Use PRISM Validator
   - Also try the BIDS Validator (separate tool)
   - Do they find the same issues? Different issues?
   - Which messages are clearer?

---

## Key Learnings

### **Error Types You'll See**

```
Format Errors:        encoding, delimiters
Structure Errors:     missing columns, missing files  
Value Errors:         out-of-range, duplicates, typos
Metadata Errors:      incomplete descriptions, missing info
```

### **Prevention Strategy**

```
Data Collection
        ↓
    VALIDATE (catch errors here!)
        ↓
Data Analysis (now confident data is clean!)
        ↓
    Publication & Sharing
```

### **Real-World Impact**

- **10-40% of raw data files** have at least one error
- **Catching errors early** saves 10-100x the time vs. finding them later
- **Validation reports** serve as documentation for data cleaning
- **Clean data** = trustworthy results = publishable science

---

## Checklist: Ready for Next Exercise?

- [ ] Loaded at least 5 bad files and observed what happened
- [ ] Used the Validator on the bad_examples folder
- [ ] Found at least 3 different error types
- [ ] Understand the difference between Errors, Warnings, and Info messages
- [ ] Could explain to someone else how to identify and fix a data quality issue

---

## Quick Reference: Common Error Messages

| Message | Means | Fix |
|---------|-------|-----|
| "File too large" | File exceeds size limit | Use smaller subset or compress |
| "No data rows" | Headers only, no actual data | Add data or check file |
| "Duplicate IDs" | Same participant appears > 1 time | Remove/merge duplicate |
| "Column mismatch" | Wrong delimiter or missing columns | Check delimiters and headers |
| "Invalid date" | Date format not recognized | Use YYYY-MM-DD format |
| "Out of range" | Value outside expected bounds | Validate actual value |
| "Encoding error" | Character encoding is wrong | Save as UTF-8 |
| "Missing required column" | Column needed is not present | Add the column |

---

## Next Steps

🎉 **Great work!** You've learned that **data validation catches problems BEFORE they cause analysis errors.**

**In Exercise 3: Participant Mapping**, you'll:
- Take the demographic data we imported
- Learn how to transform custom encodings (1→M, 2→F) to standard formats
- Create mapping specifications for automated transformations
- Generate standardized participants.tsv files

**Ready?** → Go to `../exercise_2_participant_mapping/INSTRUCTIONS.md`

---

## Instructor Notes

**Common discoveries students make:**
1. "I didn't know validation could catch encoding issues!"
2. "That duplicate ID would have ruined my analysis!"
3. "The error message was actually really helpful once I learned to read it"
4. "Validation should happen immediately after data collection"

**Discussion points:**
- Why don't data collection tools validate by default?
- How does this relate to reproducibility and open science?
- What would happen if journals required validation reports?
