# Exercise 2: Hunting for Errors

**Time:** 25 minutes  
**Goal:** Learn how to identify and understand common data issues using the PRISM Validator.

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Use the PRISM Validator to check for errors
- ✓ Understand different types of validation messages (Error, Warning, Info)
- ✓ Identify common pitfalls in raw data (formatting, types, ranges)
- ✓ Discover how PRISM helps you catch issues before they ruin your analysis

---

## Starting Materials

Look in the `bad_examples/` folder inside this exercise. It contains 13 files, each with at least one deliberate error or "messy" feature.

---

## Your Task: The Bug Hunt

Instead of following a script, your goal is to explore these files and see what PRISM tells you about them.

### Step 1: Loading the "Messy" Files
1. Open **PRISM Studio** (http://localhost:5001)
2. Go to the **Converter** → **Survey Data Converter**
3. Select any file from the \`bad_examples/\` folder and click **"Upload"**.

### Step 2: Investigate
For each file you load, ask yourself:
- **Does it load at all?** (Some files have fundamental formatting issues).
- **Does the Preview look right?** (Check the columns and rows).
- **What happens when you try to map columns?** (Are some columns missing or weirdly named?).
- **Are there any warnings or errors on the screen?** (Look for red or orange boxes).

### Step 3: Specific Challenges
Can you find the files that have these specific problems?
- A file that isn't actually tab-separated (TSV).
- A file where a participant appears twice.
- A file where someone entered a number that is "impossible" for that scale.
- A file that is completely empty.

---

## Exercise 2 Challenge

Pick one of the "broken" files. Try to identify exactly what is wrong, and if you're feeling adventurous, open the file in a text editor (like Notepad or VS Code), fix the problem, and try uploading it again to see if it passes!

---

**Next Steps:**
Once you've mastered the art of finding bugs, let's look at how to process clean data.

**Ready for Exercise 3?** → Go to \`../exercise_3_using_recipes/\`
