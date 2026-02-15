# Exercise 4: Use Recipes to Score & Export Data

**⏱ Time:** 20 minutes  
**🎯 Goal:** Apply automated scoring recipes and export analysis-ready data to SPSS format

**📚 Concepts:** Automated scoring, recipes, composite scores, data export, SPSS integration

---

## What You'll Learn

By the end of this exercise, you will:
- ✅ Understand what scoring recipes are and why they're useful
- ✅ Apply recipes to calculate total scores automatically
- ✅ Export data to SPSS (.sav) format with complete metadata
- ✅ Generate codebooks from recipes
- ✅ Verify scoring accuracy

---

## What Are Recipes?

A **recipe** is a JSON file that defines how to calculate scores from raw survey items.

### **Simple Example: Wellbeing Total Score**

**Raw survey items:**
```
WB01 = 4
WB02 = 4
WB03 = 2
WB04 = 3
WB05 = 4
```

**Recipe says:** "Sum all five items"

**Result:**
```
WB_total = 4 + 4 + 2 + 3 + 4 = 17
```

### **Why Recipes?**

| Without Recipe | With Recipe |
|---|---|
| Calculate scores manually for 100 participants | Apply once, get all 100 scores |
| Easy to make errors | Consistent, traceable calculation |
| Hard to remember which items to sum | Documented in JSON file |
| No metadata about how score was created | Full documentation included |

**Recipes automate repetitive calculations and ensure consistency!**

---

## The Wellbeing Recipe

Your workshop includes a pre-made recipe file:  
`exercises/workshop/exercise_3_using_recipes/recipe-wellbeing.json`

### **What it contains:**

```json
{
  "metadata": {
    "name": "WHO-5 Well-Being Index Scoring",
    "version": "1.0",
    "task": "wellbeing"
  },

  "scores": {
    "wellbeing_total": {
      "description": "Total well-being score",
      "items": ["WB01", "WB02", "WB03", "WB04", "WB05"],
      "operation": "sum",
      "range": "5-25",
      "interpretation": "Higher = better well-being"
    }
  }
}
```

### **Meaning:**
- **Items:** Use these five columns
- **Operation:** Add them together (sum)
- **Result:** New variable called `wellbeing_total`
- **Range:** Expected values between 5-25 (5 items × 1-5 scale)

---

## Step 1: Access the Recipe Tool

### **In PRISM Studio:**

1. **Navigate to:** **"Tools"** → **"Recipe Scorer"** (or similar)
2. **Alternatively:** Go to **http://localhost:5001/tools/recipe-scorer**

### **Or use CLI (if you're comfortable with terminal):**

```bash
python prism.py --recipe recipe-wellbeing.json --input my_dataset/ --output derivatives/
```

---

## Step 2: Load Your Dataset

In the Recipe tool:

1. **Click "Select Dataset"**
2. **Navigate to:** `examples/workshop/exercise_1_raw_data/my_dataset/` (from Exercise 1)
3. **Verify:** You should see:
   - ✅ 9 participants (DEMO001-DEMO009)
   - ✅ 1 session (baseline)
   - ✅ WB01-WB05 columns found
   - ✅ participants.tsv recognized

---

## Step 3: Select the Recipe

1. **Click "Choose Recipe"**
2. **Navigate to:** `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json`
3. **Select it**

### **The tool should show:**
```
Recipe loaded: WHO-5 Well-Being Index Scoring
Scores to calculate:
  - wellbeing_total (sum of WB01, WB02, WB03, WB04, WB05)

Items found:
  ✓ WB01
  ✓ WB02
  ✓ WB03
  ✓ WB04
  ✓ WB05

Status: Ready to score 9 participants
```

---

## Step 4: Configure Output

### **Output Folder:**
1. Click "Set Output Directory"
2. Navigate to and select: `examples/workshop/exercise_1_raw_data/derivatives/`
3. (Create this folder if it doesn't exist)

### **Export Formats:**
Check these boxes:
- ☑ **CSV** - For Excel/spreadsheet analysis
- ☑ **SPSS (.sav)** - For SPSS software
- ☑ **Codebook (PDF)** - Documentation of scores
- ☑ **Create value labels** - For SPSS interpretation

---

## Step 5: Calculate Scores

1. **Click "Calculate Scores"**
2. **Progress bar:**  Watch as it calculates for each participant
3. **Success message:** "Successfully scored X datasets"

**What happened:**
- For each participant, calculated WB_total score
- Created output files in your derivatives folder
- Generated codebook with score information

---

## Step 6: Verify Results

After successful scoring:

### **Check the CSV output:**

```bash
cat derivatives/wellbeing_scores.csv
```

Should show:
```
participant_id,ses,WB01,WB02,WB03,WB04,WB05,wellbeing_total
DEMO001,baseline,4,4,2,3,4,17
DEMO002,baseline,3,3,3,3,3,15
DEMO003,baseline,5,5,1,5,5,21
DEMO004,baseline,2,2,4,2,2,12
...
```

### **Verify calculations:**
- DEMO001: 4+4+2+3+4 = 17 ✓
- DEMO003: 5+5+1+5+5 = 21 ✓
- DEMO004: 2+2+4+2+2 = 12 ✓

**All correct? Then your recipe works!**

### **Check the SPSS file:**

PRISM created: `wellbeing_scores.sav`

If you have SPSS or Jamovi installed:
1. Open the `.sav` file
2. Check that wellbeing_total is a new variable
3. Values should range from 5-25
4. Value labels should be readable

### **Check the codebook:**

`wellbeing_scores_codebook.pdf` should contain:
- WHO-5 instrument information
- Item descriptions (what each question asked)
- Scoring formula
- Score interpretation ranges

**This codebook is perfect for methods sections!**

---

## Understanding the Scores

### **WHO-5 Score Interpretation:**

| Range | Interpretation |
|-------|-----------------|
| 25 | Perfect well-being (maximum) |
| 20-24 | Excellent well-being |
| 13-19 | Moderate/typical well-being |
| 8-12 | Poor well-being |
| 5-7 | Critical well-being concerns |

### **Our Data Results:**

Looking at our 9 participants:
```
DEMO001: 17 (Moderate/typical)
DEMO002: 15 (Moderate/typical)
DEMO003: 21 (Excellent)
DEMO004: 12 (Poor)
DEMO005: 15 (Moderate/typical)
DEMO006: 16 (Moderate/typical)
DEMO007: 17 (Moderate/typical)
DEMO008: 12 (Poor)
DEMO009: 19 (Moderate/excellent)
```

**Interesting finding:** DEMO003 has the highest well-being, while DEMO004 and DEMO008 show concerns.

---

## Advanced: Creating a Custom Recipe

### **What if you want to score a different scale?**

For example, a **Stress & Anxiety Scale** with 3 items:

```json
{
  "metadata": {
    "name": "Stress & Anxiety Total",
    "version": "1.0",
    "task": "stress"
  },
  
  "scores": {
    "stress_anxiety_total": {
      "description": "Total stress and anxiety score",
      "items": ["ST01", "ST02", "ST03"],
      "operation": "mean",
      "range": "1-5",
      "interpretation": "Higher = more stress/anxiety"
    },
    
    "stress_only": {
      "description": "Stress items only",
      "items": ["ST01", "ST02"],
      "operation": "sum",
      "range": "2-10",
      "interpretation": "Specific stress measure"
    }
  }
}
```

**Key operations:**
- `sum` - Add items
- `mean` - Average items
- `count` - Count how many items were answered
- `reverse` - Reverse-code an item first, then sum

---

## Bonus Challenge: Multi-Scale Scoring

What if your dataset has multiple surveys?

### **Extended Recipe:**

```json
{
  "metadata": {
    "name": "Comprehensive Psychological Assessment"
  },
  
  "scores": {
    "wellbeing_total": {
      "items": ["WB01", "WB02", "WB03", "WB04", "WB05"],
      "operation": "sum"
    },
    
    "anxiety_total": {
      "items": ["ANX01", "ANX02", "ANX03", "ANX04", "ANX05", "ANX06", "ANX07"],
      "operation": "sum"
    },
    
    "depression_total": {
      "items": ["DEP01", "DEP02", ..., "DEP09"],
      "operation": "sum"
    }
  }
}
```

**Result:** One recipe calculates three different scores!

---

## Step 7: Export to SPSS for Analysis

### **If you have SPSS:**

1. Open `wellbeing_scores.sav` in SPSS
2. All scores are calculated and ready
3. Value labels are included for reference
4. Metadata shows how scores were created
5. You can immediately start statistical analysis

### **If you use R:**

```r
# Load scored data
library(haven)
data <- read_sav("wellbeing_scores.sav")

# Quick analysis
summary(data$wellbeing_total)

# Visualization
hist(data$wellbeing_total, main="WHO-5 Scores")
```

### **If you use Python:**

```python
import pandas as pd

# Load CSV output
data = pd.read_csv("wellbeing_scores.csv")

# Descriptive statistics
print(data['wellbeing_total'].describe())

# By demographic group
print(data.groupby('sex')['wellbeing_total'].mean())
```

---

## Checklist: Ready for Next Exercise?

- [ ] Recipe loaded successfully
- [ ] Scores calculated for all 9 participants
- [ ] Wellbeing_total values range from 5-25
- [ ] CSV and SPSS files generated in derivatives/
- [ ] Codebook created with instrument information
- [ ] Can explain how WHO-5 scores are interpreted

---

## Key Concepts

### **What recipes enable:**
1. **Reproducibility** - Same calculation every time
2. **Transparency** - Anyone can see the formula
3. **Automation** - No manual calculation needed
4. **Consistency** - All participants scored identically
5. **Documentation** - Codebook included automatically

### **Typical recipe operations:**
```
Sum:     Add all items
Mean:    Average all items
Count:   How many answered (out of max)
Reverse: Flip scale before summing (5→1, 4→2, etc.)
```

### **Best practices for recipes:**
- ✅ Include metadata (instrument name, authors, year)
- ✅ Document data range and interpretation
- ✅ Test with a few participants first
- ✅ Keep a copy in your project for reproducibility
- ✅ Version control the recipe file (git)

---

## Common Issues & Solutions

| Problem | Solution |
|---------|----------|
| "Items not found" | Check item names match exactly (case-sensitive, WB01 not wb01) |
| "Scores out of range" | Verify items are numeric, not text |
| "SPSS file won't open" | Make sure you have recent SPSS version or try Jamovi (free) |
| "Codebook looks wrong" | Check recipe metadata spelling and format |

---

## Next Steps

🎉 **Excellent!** Your data is scored and ready for analysis!

Notice that we've now completed a full workflow:
1. ✅ Project setup (Exercise 0)
2. ✅ Data import (Exercise 1)
3. ✅ Error hunting (Exercise 2)
4. ✅ Demographic mapping (Exercise 3)
5. ✅ Scoring (Exercise 4)

**In Exercise 5: Creating Templates**, you'll:
- Learn to create metadata templates from scratch
- Make your survey self-documenting
- Generate reusable templates for future projects
- Validate templates against PRISM schemas

**Ready?** → Go to `../exercise_4_templates/INSTRUCTIONS.md`

---

## Real-World Example: Multi-Site Study

Imagine 5 research sites collecting data:
- All use different analysis software (SPSS, R, Python, Stata, Excel)
- All implement scoring slightly differently
- Result: Inconsistent scores across sites!

**With recipes:**
- All sites use the same recipe file
- All scores identical regardless of tool
- Can confidently combine 5 sites' data
- Scoring method documented and shareable

**This is how 1000+ person studies maintain quality!**

---

## Appendix: Recipe JSON Structure

**Complete recipe template:**

```json
{
  "metadata": {
    "name": "Instrument Name",
    "abbreviation": "ABBR",
    "version": "1.0",
    "task": "taskname",
    "authors": ["Name1", "Name2"],
    "year": 2025,
    "reference": "Citation information",
    "doi": "doi:xx.xxxx/xxxxx"
  },
  
  "scores": {
    "score_name": {
      "description": "What this score measures",
      "items": ["IT01", "IT02", "IT03"],
      "operation": "sum|mean|count|reverse",
      "reverse_items": ["IT02"],  // if needed
      "range": "X-Y",
      "interpretation": "How to interpret values",
      "clinical_cutoffs": {
        "normal": "X-Y",
        "mild": "Y-Z",
        "severe": "Z-..."
      }
    }
  }
}
```

This structure ensures your recipes are completely documented!
