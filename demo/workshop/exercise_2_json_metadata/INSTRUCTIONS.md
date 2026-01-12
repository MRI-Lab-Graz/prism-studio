# Exercise 2: Validation & Troubleshooting

**Time:** 25 minutes  
**Goal:** Learn how to identify and understand common data issues using the PRISM Validator.

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Use the PRISM Validator to check for errors
- ✓ Understand different types of validation messages (Error, Warning, Info)
- ✓ Identify common pitfalls in raw data (formatting, types, ranges)
- ✓ Learn how to use the logs to troubleshoot conversion failures

---

## Starting Materials

Look in the `bad_examples/` folder inside this exercise:
- This folder contains several TSV files, each with a specific "bug" or issue.
- Examples include: `wrong_delimiter.tsv`, `out_of_range_values.tsv`, `missing_id_column.tsv`, etc.

---

## Your Task

Try to "convert" or "validate" these files and observe how PRISM handles the errors.

---

## Step-by-Step Instructions

### Step 1: Attempting to Convert "Broken" Data

1. Open **PRISM Studio** (http://localhost:5001)
2. Go to the **Converter** → **Survey Data Converter**
3. Try loading `01_missing_id_column.tsv`
4. **Observe:** Does the system let you proceed? Can you find a column to map to `participant_id`?

### Step 2: Testing Data Quality (Validation)

1. Load `04_out_of_range_values.tsv` in the converter.
2. Map the columns as you did in Exercise 1. (Select `participant_id`, `session`, task name `wellbeing`, modality `survey`).
3. Click "Preview" or attempt to convert.
4. **Observe:** Look for warnings about values being outside the expected scale.

### Step 3: Troubleshooting Parsing Errors

1. Try loading `02_wrong_delimiter.tsv`.
2. Notice how the preview looks. Does it see multiple columns, or just one big block of text?
3. This is what happens when TSV files use semicolons or commas instead of tabs.

### Step 4: Exploring Other Issues

Try the following files and see what messages appear:
- `07_duplicate_ids.tsv` (Two rows for the same participant)
- `10_empty_file.tsv` (Nothing to process)
- `13_wrong_id_format.tsv` (IDs that don't match the `sub-XXX` pattern)

---

## Discussion Point: Why Validate?

Validation isn't just about making the tools happy. It's about:
- **Data Integrity:** Ensuring your Likert scales don't have impossible values (like a "99" on a 1-5 scale).
- **Findability:** Ensuring participants are named consistently so they can be merged with other data.
- **Reproducibility:** Catching "messy" data early before it reaches your analysis script.

---

## Exercise 2 Challenge

Pick one of the files in `bad_examples/` and try to "fix" it by renaming it or editing its content (if you have a text editor open) so that it passes validation.

---

**Next Steps:**
Once you've seen how PRISM catches errors, let's move on to the final exercise!

**Ready for Exercise 3?** → Go to `../exercise_3_recipes_export/`
