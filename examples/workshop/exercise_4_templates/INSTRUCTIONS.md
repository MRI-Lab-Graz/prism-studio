# Exercise 5: Create Reusable Metadata Templates

**⏱ Time:** 20 minutes  
**🎯 Goal:** Create and validate a WHO-5 metadata template for reuse across datasets

**📚 Concepts:** Metadata, JSON schemas, template creation, documentation, reusability

![Exercise 4 UI (Light Mode)](../../../docs/_static/screenshots/prism-studio-exercise-4-templates-light.png)

---

## What You'll Learn

By the end of this exercise, you will:
- ✅ Understand what metadata templates are and why they matter
- ✅ Create a WHO-5 survey template in PRISM format
- ✅ Add detailed item descriptions and scale information
- ✅ Validate templates against PRISM schemas
- ✅ Reuse templates across multiple datasets

---

## What Are Templates?

A **template** is a reusable JSON file that documents a survey/instrument completely.

### **The Problem:**

When you imported your data in Exercise 1, PRISM created `.json` sidecar files. But they were mostly empty:

```json
{
  "participant_id": "DEMO001",
  "session": "baseline"
}
```

**Missing information:**
- What do the survey items actually ask?
- What do the response values mean?
- What's the valid range?
- How is the score interpreted?
- Who created this survey? Citation?

### **The Solution: Templates**

A template provides all this information once:

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "Language": "en",
    "Respondent": "self"
  },
  
  "Study": {
    "TaskName": "wellbeing",
    "OriginalName": "WHO-5 Well-Being Index",
    "NumberOfItems": 5,
    "Authors": ["Topp", "Østergaard", "Søndergaard", "Bech"],
    "Year": 2015,
    "Citation": "Topp et al. (2015) The WHO-5 Well-Being Index..."
  },
  
  "WB01": {
    "Description": "I have felt cheerful and in good spirits",
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  },
  ...
}
```

### **Benefits:**

| Benefit | Why It Matters |
|---------|---|
| **Documentation** | Anyone reading your data knows exactly what each item means |
| **Standardization** | All datasets using this survey use identical documentation |
| **Reusability** | Apply same template to future studies |
| **Sharing** | Collaborators instantly understand your instrument |
| **Archiving** | Data is self-documenting when archived |
| **Reproducibility** | Someone could reimplement your study exactly |

---

## Starting Point: Official Template

An official WHO-5 template already exists in PRISM:  
`official/library/survey/survey-wellbeing.json`

Let's examine it to learn the structure, then create a customized version for your workshop dataset.

---

## Step 1: Examine the Official Template

### **On your computer:**

1. **Navigate to:** `official/library/survey/survey-wellbeing.json`
2. **Open in a text editor** (VS Code, Sublime, Notepad++, or even Notepad)
3. **Scan the structure:**
   - Top level: `Technical`, `Metadata`, `Study`
   - Items: `WB01` through `WB05`
   - Each item has: Description, Levels, Reversed flag

---

## Step 2: Understand Template Structure

### **Section 1: Technical Details**

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "Language": "en",
    "Respondent": "self"
  }
}
```

| Field | Example | Meaning |
|-------|---------|---------|
| StimulusType | "Questionnaire" | Is it a survey, task, stimulus, etc.? |
| FileFormat | "tsv" | Data format (tab-separated) |
| Language | "en" | Survey language code |
| Respondent | "self" | Who answers? (self, proxy, observer, etc.) |

### **Section 2: Study Metadata**

```json
{
  "Study": {
    "TaskName": "wellbeing",
    "Abbreviation": "WB",
    "Authors": ["Topp", "Østergaard", "Søndergaard", "Bech"],
    "Year": 2015,
    "DOI": "10.1159/000376585",
    "Citation": "Topp, C.W., et al. (2015). The WHO-5...",
    "NumberOfItems": 5,
    "License": "CC-BY-4.0",
    "Source": "https://www.psytoolkit.org/survey-library/who5.html"
  }
}
```

Key information for researchers to understand the instrument!

### **Section 3: Item Descriptions**

```json
{
  "WB01": {
    "Description": "I have felt cheerful and in good spirits",
    "Reversed": false,
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  }
}
```

For each item:
- **Description**: Exact wording of question
- **Reversed**: Is this item reverse-coded? (some scales flip values before summing)
- **Levels**: What each numeric value means

---

## Step 3: Create Your Custom Workshop Template

Now you'll create a custom version tailored to your workshop dataset.

### **File Location:**
`examples/workshop/exercise_4_templates/`

### **File Name:**
`survey-wellbeing-workshop.json`

### **Content: Basic Structure**

```json
{
  "Technical": {
    "StimulusType": "Questionnaire",
    "FileFormat": "tsv",
    "Language": "en",
    "Respondent": "self"
  },

  "Metadata": {
    "SchemaVersion": "1.1.1",
    "CreatedDate": "2025-02-15",
    "Creator": "PRISM Workshop Participant",
    "Notes": "Created during hands-on workshop for learning purposes"
  },

  "Study": {
    "TaskName": "wellbeing",
    "OriginalName": {
      "en": "WHO-5 Well-Being Index (Adapted)"
    },
    "Abbreviation": "WB",
    "Authors": ["Topp", "Østergaard", "Søndergaard", "Bech"],
    "Year": 2015,
    "DOI": "10.1159/000376585",
    "Citation": "Topp, C.W., Østergaard, S.D., Søndergaard, S., & Bech, P. (2015). The WHO-5 Well-Being Index: A Systematic Review of the Literature. Psychotherapy and Psychosomatics, 84(3), 167-176.",
    "NumberOfItems": 5,
    "License": {
      "en": "Freely available for research purposes"
    },
    "LicenseID": "CC-BY-4.0",
    "Source": "https://www.psytoolkit.org/survey-library/who5.html",
    "Instructions": {
      "en": "Please indicate for each of the five statements which is closest to how you have been feeling over the last two weeks. Notice that higher numbers mean better well-being."
    }
  },

  "WB01": {
    "Description": {
      "en": "I have felt cheerful and in good spirits"
    },
    "Reversed": false,
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  },

  "WB02": {
    "Description": {
      "en": "I have felt calm and relaxed"
    },
    "Reversed": false,
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  },

  "WB03": {
    "Description": {
      "en": "I have felt active and vigorous"
    },
    "Reversed": false,
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  },

  "WB04": {
    "Description": {
      "en": "I woke up feeling fresh and rested"
    },
    "Reversed": false,
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  },

  "WB05": {
    "Description": {
      "en": "My daily life has been filled with things that interest me"
    },
    "Reversed": false,
    "Levels": {
      "0": "At no time",
      "1": "Some of the time",
      "2": "Less than half the time",
      "3": "More than half the time",
      "4": "Most of the time",
      "5": "All of the time"
    }
  }
}
```

---

## Step 4: Use the Template Editor

PRISM Studio includes a JSON Template Editor for creating/editing templates visually.

### **In PRISM Studio:**

1. **Go to:** **"Tools"** → **"JSON Template Editor"**
2. **Or direct URL:** http://localhost:5001/tools/template-editor

### **Using the editor:**

1. **Select Modality:** `survey`
2. **Load existing template OR start new**
3. **Edit fields:**
   - Task name, authors, description
   - Add items with descriptions
   - Define response levels
   - Validate against schema

4. **Save:** Template is saved as JSON

---

## Step 5: Validate Your Template

After creating, validate that it follows PRISM specifications:

### **Option A: Automatic Validation (in editor)**

In the Template Editor:
1. **Click "Validate Template"**
2. **Check results:**
   - ✅ No errors = valid!
   - ⚠️ Warnings = check spelling/formatting
   - ❌ Errors = fix before using

### **Option B: Manual Validation**

Check these things:
- [ ] All required fields present (`Technical`, `Study`, items)
- [ ] JSON syntax correct (opening/closing braces, commas)
- [ ] Item names match your data (WB01-WB05)
- [ ] Levels are 0-5 (matching your data scale)
- [ ] No typos in descriptions
- [ ] Authors and citations present

### **Option C: PRISM CLI Validation**

```bash
python prism.py --validate-template survey-wellbeing-workshop.json
```

---

## Step 6: Apply Template to Your Dataset

Once validated, apply your template to add metadata to all your survey files:

### **In PRISM Studio:**

1. **Go to:** **"Tools"** → **"Apply Template"**
2. **Select:**
   - Dataset: `examples/workshop/exercise_1_raw_data/my_dataset/`
   - Template: `survey-wellbeing-workshop.json`
3. **Click "Apply"**

### **Result:**

All JSON sidecar files are updated with your template information:

```bash
# Before (empty)
head -n 5 sub-DEMO001_ses-baseline_task-wellbeing_survey.json
{}

# After (enriched with template)
head -n 20 sub-DEMO001_ses-baseline_task-wellbeing_survey.json
{
  "Description": "I have felt cheerful and in good spirits",
  "TaskName": "wellbeing",
  "Authors": ["Topp", "Østergaard"],
  "Levels": {
    "0": "At no time",
    "1": "Some of the time",
    ...
  }
}
```

---

## Step 7: Share Your Template

Now you have a reusable template!

### **How to use it for future studies:**

```
New Study (2026):
- Same WHO-5 survey
- Different participants
- Use: survey-wellbeing-workshop.json

Result: All documentation identical across studies!
```

### **Share with collaborators:**

```
Email template file to collaborators:
"Please use this template for your WHO-5 data: 
attached survey-wellbeing-workshop.json"

They can immediately understand your instrument!
```

### **Archive with publication:**

Include template in supplementary materials:
```
Supplementary Materials:
├── survey-wellbeing-workshop.json (template)
├── recipe-wellbeing.json (scoring)
├── participants_mapping.json (encodings)
└── dataset_description.json (study info)
```

Readers can understand EXACTLY how you collected and processed data!

---

## Template Best Practices

### **1. Be Descriptive**
```json
// ❌ Not helpful
"WB01": { "Description": "Item 1" }

// ✅ Better
"WB01": { "Description": "I have felt cheerful and in good spirits" }
```

### **2. Include Full Citations**
```json
// ❌ Minimal
"Citation": "WHO-5"

// ✅ Complete
"Citation": "Topp, C.W., Østergaard, S.D., Søndergaard, S., & Bech, P. (2015). The WHO-5 Well-Being Index: A Systematic Review of the Literature. Psychotherapy and Psychosomatics, 84(3), 167-176."
```

### **3. Add Interpretation Guidance**
```json
{
  "Study": {
    "Scoring": {
      "Range": "5-25",
      "Interpretation": {
        "5-7": "Critical well-being concerns",
        "8-12": "Poor well-being",
        "13-19": "Moderate well-being",
        "20-24": "Excellent well-being",
        "25": "Perfect well-being"
      }
    }
  }
}
```

### **4. Version Control**
```json
{
  "Metadata": {
    "SchemaVersion": "1.1.1",
    "TemplateVersion": "1.0",
    "CreatedDate": "2025-02-15",
    "LastModified": "2025-02-15"
  }
}
```

---

## Advanced: Multilingual Templates

You can create templates in multiple languages:

```json
{
  "WB01": {
    "Description": {
      "en": "I have felt cheerful and in good spirits",
      "de": "Ich habe mich froh und guter Laune gefühlt",
      "fr": "Je me suis senti(e) gai(e) et de bonne humeur",
      "es": "He estado alegre y de buen humor"
    }
  }
}
```

This makes your data truly internationally accessible!

---

## Checklist: Ready for Next Workshop Activity?

- [ ] Created `survey-wellbeing-workshop.json`
- [ ] Validated template (no errors reported)
- [ ] Applied template to dataset
- [ ] All 5 items described with full question wording
- [ ] Response levels documented (0-5)
- [ ] Authors and citations included
- [ ] Template is valid JSON (can open, parse correctly)

---

## Key Takeaways

### **What you accomplished:**

1. ✅ Created reusable metadata documentation
2. ✅ Followed PRISM/BIDS data schema standards
3. ✅ Made your data self-documenting
4. ✅ Created shareable template for collaborators
5. ✅ Enabled reproducible research

### **Templates are the final piece of rigorous research:**

```
Data Collection
    ↓
Validation (Exercise 2) ✓
    ↓
Standardization (Exercise 3) ✓
    ↓
Scoring (Exercise 4) ✓
    ↓
Documentation (Exercise 5) ✓
    ↓
RESEARCH READY!
```

---

## Next Steps: Congratulations!

🎉 **You've completed the entire PRISM workshop!**

You now know how to:
1. ✅ Organize projects professionally (YODA)
2. ✅ Convert raw data to standard formats
3. ✅ Validate data quality
4. ✅ Standardize demographic data
5. ✅ Automatically score assessments
6. ✅ Create reusable documentation

**What's next?**
- **Apply this workflow** to your own research
- **Share templates** with your lab/collaborators
- **Advocate for data quality** in your field
- **Publish your data** with full documentation
- **Teach others** this workflow

---

## Real-World Impact

**The six exercises you've completed are how professional research is done:**

- Data scientists use YODA structure
- Computational biologists validate data
- Clinical researchers standardize encodings
- Neuroscience labs share recipes
- Open science initiatives require templates

**You're now trained in best practices!**

---

## Optional: Explore Official Template Library

Visit: `official/library/survey/`

You'll find:
- `survey-wellbeing.json` - WHO-5 (we learned this!)
- `survey-phq9.json` - PHQ-9 (Depression)
- `survey-gad7.json` - GAD-7 (Anxiety)
- 50+ more instruments

**Challenge:** Pick another template and understand its structure. Could you create your own version?

---

## Appendix: Complete Template JSON Structure

```json
{
  "Technical": {
    "StimulusType": "string",
    "FileFormat": "tsv|csv|json",
    "Language": "ISO code (en, de, fr, etc)",
    "Respondent": "self|proxy|observer"
  },

  "Metadata": {
    "SchemaVersion": "string",
    "CreatedDate": "YYYY-MM-DD",
    "Creator": "string",
    "Notes": "string"
  },

  "Study": {
    "TaskName": "lowercase_task_name",
    "OriginalName": { "en": "Full name", "de": "Vollständiger Name" },
    "Abbreviation": "ABBR",
    "Authors": ["First", "Author", "Names"],
    "Year": 2025,
    "DOI": "10.xxxx/xxxxx",
    "Citation": "Full citation",
    "NumberOfItems": 5,
    "License": { "en": "description" },
    "LicenseID": "CC-BY-4.0",
    "Source": "URL",
    "Instructions": { "en": "Survey instructions" }
  },

  "ITEM01": {
    "Description": { "en": "Item text" },
    "Reversed": false,
    "Levels": {
      "0": "Label",
      "1": "Label",
      "..." : "..."
    }
  }
}
```

Everything you need to document any instrument!
