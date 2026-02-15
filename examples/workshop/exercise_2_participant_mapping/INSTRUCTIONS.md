# Exercise 3: Map & Standardize Demographic Data

**⏱ Time:** 45 minutes  
**🎯 Goal:** Create a mapping specification to transform custom demographic encodings to standard formats

**📚 Concepts:** Data transformation, encoding standards, JSON specifications, automated mapping, data normalization

---

## What You'll Learn

By the end of this exercise, you will:
- ✅ Understand why demographic encoding standardization matters
- ✅ Create a `participants_mapping.json` specification file
- ✅ Map custom encodings to standard PRISM/BIDS values
- ✅ Use PRISM to automatically generate standardized participants.tsv
- ✅ Document your data transformations for reproducibility

---

## The Problem: Custom Encodings

When you exported the wellbeing survey data, the demographic variables used **numeric codes**:

```
sex:         1 = Male, 2 = Female, 4 = Other
education:   1-6 scale (1=Primary, 6=Graduate)
handedness:  1 = Right, 2 = Left
```

But PRISM/BIDS standards expect:

```
sex:         M, F, O, or X  (letters)
education:   1-6 (consistent with original)
handedness:  R, L, A (Right, Left, Ambidextrous)
```

**The mapping file tells PRISM:** "When you see '1' in the sex column, transform it to 'M'"

---

## Why Mapping Matters

### **Scenario: Without Mapping**
```
Researcher A's data:    sex = [1, 2, 4]
Researcher B's data:    sex = [M, F, O]
Researcher C's data:    sex = [0, 1, 2]

Result: CHAOS! Are they the same variable? Different studies?
```

### **Scenario: With Mapping**
```
Researcher A's data:    sex = [1, 2, 4]
                           ↓ Apply mapping JSON
                        M, F, O
Researcher B's data:    sex = [M, F, O]
                           (already mapped)
Researcher C's data:    sex = [0, 1, 2]
                           ↓ Apply their mapping JSON
                        M, F, O

Result: All standardized! Can be compared directly.
```

---

## The Raw Data: What We're Starting With

From Exercise 1, your `participants.tsv` has:

```
participant_id    age    sex    education    handedness
DEMO001          28     2      4            1
DEMO002          34     1      5            1
DEMO003          22     2      3            1
DEMO004          45     1      6            2
...
```

**Problem:** Column `sex` has values 1, 2, 4. But what do they mean?
- Column `education` has values 1-6. What do they represent?

**Solution:** Create a mapping file that documents and transforms these.

---

## Step 1: Examine Your Data

### **Look at what you have:**

1. Open the file `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.tsv` in a text editor or spreadsheet
2. Look at the first 10 rows (header + 9 participants)
3. Note down all unique values in these columns:
   - `sex`: What values appear? (1, 2, 4 probably)
   - `education`: What values appear? (likely 1-6)
   - `handedness`: What values appear? (1, 2 probably)

### **Document your findings:**

```
sex values found:     _______________
education values:     _______________
handedness values:    _______________
```

---

## Step 2: Create the Mapping Specification

Now you'll create a `participants_mapping.json` file that documents the encoding.

### **File Location:**
Create this file in: `examples/workshop/exercise_2_participant_mapping/`

### **File Name:**
`participants_mapping.json`

### **Content Structure:**

```json
{
  "sex": {
    "encoding": "numeric",
    "description": "Biological sex of participant",
    "mappings": {
      "1": "M",
      "2": "F",
      "4": "O"
    },
    "missing_value": "null"
  },

  "education": {
    "encoding": "ordinal",
    "description": "Highest education level completed",
    "scale": "1=Primary, 2=Secondary, 3=Some College, 4=Bachelor, 5=Master, 6=PhD",
    "note": "No transformation needed - already standardized"
  },

  "handedness": {
    "encoding": "numeric",
    "description": "Hand dominance",
    "mappings": {
      "1": "R",
      "2": "L"
    },
    "note": "A (ambidextrous) not observed in this dataset"
  }
}
```

### **What each section means:**

| Field | Purpose | Example |
|-------|---------|---------|
| `Column name` | The column in your TSV to transform | `"sex"` |
| `encoding` | Type of encoding used | `"numeric"` or `"ordinal"` |
| `description` | What the variable represents | `"Biological sex"` |
| `mappings` | Dict of old→new values | `{"1": "M", "2": "F"}` |
| `scale` | (Optional) Explanation of scale | `"1=Primary, 2=Secondary..."` |
| `note` | (Optional) Additional info | `"Ambidextrous not in data"` |

---

## Step 3: Understand the Mapping

Let's break down what happens:

### **Original Data Row:**
```
participant_id: DEMO001
sex: 2
education: 4
handedness: 1
```

### **Mapping Specification:**
```json
{
  "sex": {"mappings": {"1": "M", "2": "F", "4": "O"}},
  "education": { /* no change */ },
  "handedness": {"mappings": {"1": "R", "2": "L"}}
}
```

### **After Applying Mapping:**
```
participant_id: DEMO001
sex: F
education: 4
handedness: R
```

**Result:** Demographic data is now in standard format!

---

## Step 4: Use PRISM's Mapping Tool

Once you've created the `participants_mapping.json` file:

### **Option A: Automatic (If PRISM has mapping feature)**

1. **In PRISM Studio:**
   - Go to: **"Tools"** → **"Participant Mapper"** (if available)
   - Or: **"Converter"** → **"Apply Mappings"**

2. **Select inputs:**
   - Original participants.TSV
   - Your mapping JSON file

3. **Generate output:**
   - New `participants.tsv` with mapped values
   - Saved to your `derivatives/` folder

### **Option B: Manual (Spreadsheet approach)**

If PRISM doesn't have a dedicated feature:

1. Open `participants.tsv` in Excel/Numbers
2. Create new columns: `sex_mapped`, `handedness_mapped`
3. Use formulas to transform values:
   - Excel: `=IF(F2=1,"M",IF(F2=2,"F","O"))`
4. Save as new file

### **Option C: Python Script (If comfortable with coding)**

```python
import pandas as pd
import json

# Load data and mapping
df = pd.read_csv('participants.tsv', sep='\t')
with open('participants_mapping.json') as f:
    mapping = json.load(f)

# Apply transformations
for col, spec in mapping.items():
    if 'mappings' in spec and col in df.columns:
        df[col] = df[col].astype(str).map(spec['mappings'])

# Save result
df.to_csv('participants_mapped.tsv', sep='\t', index=False)
```

---

## Step 5: Verify the Transformation

After applying the mapping, check that:

### **1. File structure is correct:**
- [ ] New participants.tsv exists
- [ ] Has the same columns as original
- [ ] Same number of rows (9 participants in our case)

### **2. Sex column transformed:**
- [ ] No more values of "1", "2", or "4"
- [ ] Only "M", "F", "O" appear
- [ ] Each participant has exactly one value

### **3. Handedness column transformed:**
- [ ] No more values of "1" or "2"
- [ ] Only "R" or "L" appear
- [ ] All participants have a value

### **4. Education column unchanged:**
- [ ] Still contains 1-6 values
- [ ] No changes applied
- [ ] All participants have a value

### **Sample output:**
```
participant_id    age    sex    education    handedness
DEMO001          28     F      4            R
DEMO002          34     M      5            R
DEMO003          22     F      3            R
DEMO004          45     M      6            L
```

---

## Step 6: Document Your Mapping

For reproducibility, keep notes on your transformation:

### **Create a `MAPPING_NOTES.md` file:**

```markdown
# Participant Mapping Notes

## Original Data Source
- File: wellbeing.tsv
- Date created: 2025-01-15
- Collection tool: Qualtrics

## Variables Transformed

### sex
- Original encoding: numeric (1, 2, 4)
- Mapping:
  - 1 → M (Male)
  - 2 → F (Female)
  - 4 → O (Other)
- Decision: Used BIDS standard letter codes for clarity

### handedness
- Original encoding: numeric (1, 2)
- Mapping:
  - 1 → R (Right)
  - 2 → L (Left)
- Decision: Extended BIDS standard; A (ambidextrous) not needed for this data

### education
- Original: 1-6 ordinal scale
- Mapping: NONE (already standardized)
- Note: Values intact. Scale: 1=Primary through 6=PhD

## Validation
- Applied mapping to all 9 participants
- No missing mappings found
- Result: standardized_participants.tsv
```

---

## Real-World Example: Multi-Site Study

**Why this matters in practice:**

```
Site A (Stockholm):
- sex: 1=Man, 2=Woman, 3=Other

Site B (Berlin):
- sex: 1=Male, 2=Female, 3=Diverse

Site C (Paris):
- sex: Male, Female, Non-binaire

All encoded differently!
But mapping files standardize them to: M, F, O

Result: Can combine all three sites' data in one analysis!
```

---

## Challenge: Missing Values

What if some participants didn't answer the sex question?

### **Handling Missing Data:**

```json
{
  "sex": {
    "mappings": {
      "1": "M",
      "2": "F",
      "4": "O"
    },
    "missing_value": null,
    "handling": "leave blank if missing in original"
  }
}
```

### **In your data:**
```
DEMO001, sex = 1 → M
DEMO002, sex = (empty) → (empty)
DEMO003, sex = 4 → O
```

**Key:** Never assume missing values! Always explicitly handle them.

---

## Bonus: Create Codebook from Mapping

Your mapping file can generate a **codebook** automatically:

```
Variable: sex
Description: Biological sex of participant
Type: Categorical
Values:
  - M: Male
  - F: Female
  - O: Other
  - Missing: (count)
```

This is useful for:
- Sharing with collaborators
- Publishing supplementary materials
- Archiving with your dataset
- Creating data dictionaries

---

## Checklist: Ready for Next Exercise?

- [ ] Created `participants_mapping.json` in the exercise folder
- [ ] Documented the mappings for sex and handedness
- [ ] Applied the mapping to generate transformed participants.tsv
- [ ] Verified all values are transformed correctly
- [ ] Created MAPPING_NOTES.md documenting decisions
- [ ] Understand why standardization matters for sharing data

---

## Key Takeaways

### **What mapping accomplishes:**
1. ✅ **Standardization** -All sites/studies use same encoding
2. ✅ **Documentation** - Clear record of transformations
3. ✅ **Automation** - Same mapping reused for future datasets
4. ✅ **Reproducibility** - Anyone can see what changed and why
5. ✅ **Integration** - Multi-site studies can combine data

### **BIDS Standards for Demographics:**
```
Approved Values for sex:
- M (Male)
- F (Female)
- O (Other)
- X (Not included)

Approved Values for handedness (in some BIDS extensions):
- R (Right)
- L (Left)
- A (Ambidextrous)
```

---

## Next Steps

🎉 **Excellent!** Your demographic data is now standardized.

**In Exercise 4: Using Recipes**, you'll:
- Take your validated, standardized dataset
- Apply scoring recipes to calculate total scores
- Export results to SPSS format for analysis
- Generate codebooks with value labels

**Ready?** → Go to `../exercise_3_using_recipes/INSTRUCTIONS.md`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Mapping file not found" | Make sure filename is exactly `participants_mapping.json` |
| "JSON syntax error" | Check commas, quotes, braces. Use online JSON validator |
| "Mapping didn't apply" | Verify column names match exactly (case-sensitive) |
| "Some values not mapped" | Add those values to the mappings section |
| "Original and mapped files have different row counts" | Something went wrong; double-check the logic |

---

## Appendix: JSON Reference

**Complete mapping file structure:**

```json
{
  "column_name": {
    "encoding": "numeric|categorical|ordinal",
    "description": "Human-readable description",
    "scale": "Optional: detailed scale information",
    "mappings": {
      "original_value": "new_value",
      "original_value": "new_value"
    },
    "missing_value": "how  to handle missing",
    "note": "Optional: any additional notes"
  }
}
```

**Valid JSON:**
- Strings in quotes: `"value"`
- Numbers without quotes: `1`, `2.5`
- Objects in braces: `{}`
- Arrays in brackets: `[]`
- Colon for key-value: `"key": "value"`
- Comma between elements: `{ "a": 1, "b": 2 }`
