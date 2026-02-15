# PRISM Workshop: Complete Data Workflow

Welcome to the PRISM hands-on workshop! This comprehensive guide takes you through a complete research data workflow using real-world survey data (WHO-5 Well-Being Index).

## 🎯 What You'll Learn

This workshop teaches the complete PRISM data validation pipeline:

| Exercise | Topic | Duration | Key Skills |
|----------|-------|----------|-----------|
| **0** | Project Setup | 15 min | YODA principles, project organization |
| **1** | Raw Data Import | 30 min | Data conversion, BIDS/PRISM structure |
| **2** | Error Hunting | 25 min | Validation, error identification |
| **3** | Participant Mapping | 45 min | Demographic encoding, data transformation |
| **4** | Using Recipes | 20 min | Automated scoring, SPSS export |
| **5** | Creating Templates | 20 min | Metadata creation, schema validation |

**Total Time:** ~2 hours (can be split across days)

---

## 📖 Quick Start for Workshop Participants

### 1. Launch PRISM Studio
```bash
# From repository root, activate environment first
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\Activate.ps1  # Windows

# Then start the application
python prism-studio.py
```

Open your browser to: **http://localhost:5001**

### 2. Follow the Exercises in Order
- Start with [Exercise 0: Project Setup](exercise_0_project_setup/INSTRUCTIONS.md)
- Continue sequentially through each folder
- Each folder contains detailed `INSTRUCTIONS.md` with step-by-step guidance

### 3. Materials Location
- **Raw Data:** `exercise_1_raw_data/raw_data/`
- **Error Examples:** `exercise_2_hunting_errors/bad_examples/`
- **Mapping Template:** `exercise_2_participant_mapping/` (includes solution)
- **Recipe File:** `exercise_3_using_recipes/recipe-wellbeing.json`
- **Survey Template:** `exercise_4_templates/survey-wellbeing.json`

---

## 📋 Workshop Structure

### Exercise 0: Project Setup (YODA Principles)
**Files:** [INSTRUCTIONS.md](exercise_0_project_setup/INSTRUCTIONS.md)

Create a professional, reproducible research project structure:
- Learn YODA (Yet anOther Data Analysis) principles
- Create organized folder hierarchy (`sourcedata/`, `rawdata/`, `code/`, `derivatives/`)
- Initialize your active PRISM project

**Learn:** Why structure matters for reproducibility and collaboration

---

### Exercise 1: Raw Data Import
**Files:** [INSTRUCTIONS.md](exercise_1_raw_data/INSTRUCTIONS.md) | Raw Data: `wellbeing.tsv`, `wellbeing.xlsx`

Convert unstructured survey data into BIDS/PRISM format:
- Use the Data Converter GUI to load survey files
- Map columns (participant_id, session, survey responses)
- Create proper BIDS file naming and folder structure
- Maintain data integrity throughout conversion

**Learn:** How PRISM enforces structured, documented data formats

---

### Exercise 2: Error Hunting (Validation)
**Files:** [INSTRUCTIONS.md](exercise_2_hunting_errors/INSTRUCTIONS.md) | Error Examples: `bad_examples/` folder

Learn to identify and understand common data issues:
- Use the PRISM Validator to check data quality
- Identify formatting errors (encoding, delimiters, types)
- Discover missing metadata
- Understand validation error categories (Error, Warning, Info)
- Learn how to fix issues discovered by validation

**Learn:** Catch data problems early before analysis

**Hint:** The `bad_examples/` folder contains 13 files with intentional errors. Can you find them all?

---

### Exercise 3: Participant Demographic Mapping
**Files:** [INSTRUCTIONS.md](exercise_2_participant_mapping/INSTRUCTIONS.md)

Transform demographic data with custom encodings to standardized format:
- Create a `participants_mapping.json` specification
- Document how raw codes map to standard values (e.g., 1→M, 2→F, 4→O for sex)
- Apply transformations automatically
- Generate standardized `participants.tsv`

**Learn:** How to preserve data provenance while standardizing formats

**Example:**
```
Raw Data: sex = [1, 2, 4]
Mapping: { "1": "M", "2": "F", "4": "O" }
Result: Standardized participants.tsv with "M", "F", "O"
```

---

### Exercise 4: Using Recipes
**Files:** [INSTRUCTIONS.md](exercise_3_using_recipes/INSTRUCTIONS.md) | Recipe: `recipe-wellbeing.json`

Calculate scores automatically and export analysis-ready data:
- Apply scoring recipes to compute total scores
- Export to SPSS format with complete metadata
- Generate codebooks
- Verify calculations are correct

**Learn:** How recipes automate repetitive analysis tasks

**Example:** WHO-5 total score = sum(WB01, WB02, WB03, WB04, WB05)

---

### Exercise 5: Creating Templates
**Files:** [INSTRUCTIONS.md](exercise_4_templates/INSTRUCTIONS.md)

Create reusable metadata templates:
- Use the Template Editor to define survey metadata
- Add item descriptions, scale ranges, and value labels
- Validate templates against PRISM schemas
- Save for reuse across datasets

**Learn:** Make data self-documenting and shareable

**Example:** WHO-5 template includes scale descriptions and clinical interpretations

---

## 📊 Workshop Data: WHO-5 Well-Being Index

**About the Instrument:**
- 5-item self-report questionnaire
- Assesses overall well-being and mental health
- Widely used in research and clinical settings
- Scoring: 0-5 per item, total range 5-35

**Items:**
- WB01: "I have felt cheerful and in good spirits"
- WB02: "I have felt calm and relaxed"
- WB03: "I have felt active and vigorous"
- WB04: "I woke up feeling fresh and rested"
- WB05: "My daily life has been filled with things that interest me"

**Data Demographics:**
- 9 participants included in raw data
- Baseline session assessment
- Variables: age, sex, education, handedness

---

## � Workshop Screenshots

All exercise instructions include screenshots of the PRISM Studio interface captured using **Heroshot** (automated screenshot tool). These show you exactly what to expect when following each step.

### Using Screenshots

- Screenshots are embedded in each exercise's INSTRUCTIONS.md
- Available in both **light** and **dark** themes
- Captured at 1440x900 resolution for clarity
- Updated automatically when PRISM Studio UI changes

### Capturing Fresh Screenshots

**Heroshot is an interactive visual tool (v0.13+)**. To configure or update screenshots:

**Step 1: Start PRISM Studio (Terminal 1)**
```bash
source .venv/bin/activate
python prism-studio.py
```

**Step 2: Launch Heroshot Visual Editor (Terminal 2)**
```bash
cd .heroshot
npx heroshot
```

**Step 3: Configure Screenshots Interactively**

A browser opens with Heroshot's visual editor:
1. Navigate to PRISM pages (e.g., `http://127.0.0.1:5001/converter`)
2. Click elements to select what to screenshot
3. Add styling/annotations visually
4. Save screenshot definitions

**Step 4: Regenerate Screenshots**

After configuration, run `npx heroshot` to regenerate all screenshots headlessly.

Output: `heroshots/` directory (auto-managed by Heroshot)

**For detailed documentation:**
- **Quick Start:** See [SCREENSHOTS_QUICK_START.md](SCREENSHOTS_QUICK_START.md)
- **Complete Guide:** See [.heroshot/HEROSHOT_SETUP.md](../../.heroshot/HEROSHOT_SETUP.md)
- **Directory Overview:** See [.heroshot/README.md](../../.heroshot/README.md)

---

### Setup Checklist
- [ ] Python 3.9+ installed with virtual environment activated
- [ ] PRISM Studio dependencies installed (`pip install -r requirements.txt`)
- [ ] Tested PRISM Studio startup on your system
- [ ] Downloaded workshop materials (you're reading this!)
- [ ] Optional: Configure Heroshot for automated screenshots (see docs)

### Facilitation Tips
1. **Set the context:** Start with Exercise 0 to establish YODA principles
2. **Show progress:** Use the validator output to motivate importance of structure
3. **Interactive teaching:** Guide participants through error hunting with guiding questions
4. **Real-world connection:** Relate mapping and recipes to their own research workflows
5. **Hands-on practice:** Ensure everyone completes at least Exercises 0-3
6. **Optional depth:** Exercises 4-5 can be demonstrated live or left for self-study

### Time Management
- **Flexible duration:** 90-120 minutes for all exercises, or split across sessions
- **Minimum viable workshop:** Exercises 0-3 (75 minutes)
- **Extended workshop:** All 6 exercises (120 minutes)

### Common Issues & Solutions

**Issue:** PRISM Studio won't open  
**Solution:** Check Python version (3.9+), ensure virtual environment activated, test port 5001 availability

**Issue:** Data not converting properly  
**Solution:** Verify TSV file uses tabs (not spaces), check column names match exactly

**Issue:** Validation errors are confusing  
**Solution:** Download the error report, explain that warnings ≠ errors, show error code documentation

---

## 📚 Reference Materials

### Official PRISM Templates & Recipes
- **Survey Template:** `../../official/library/survey/survey-wellbeing.json`
- **Recipe:** `../../official/recipe/survey/recipe-who5.json`

### Online Documentation
- **Web Interface Guide:** `../../docs/WEB_INTERFACE.md`
- **CLI Reference:** `../../docs/CLI_REFERENCE.md`
- **Recipe Creation Guide:** `../../docs/RECIPES.md`
- **BIDS Specification:** `../../docs/SPECIFICATIONS.md`

### External Resources
- **BIDS Standard:** https://bids-standard.github.io/bids-starter-kit/
- **WHO-5 Info:** https://www.psytoolkit.org/survey-library/who5.html
- **YODA Principles:** https://www.yoda-project.org/

---

## 📝 Exercise File Structure

```
examples/workshop/
├── README.md (you are here!)
├── STRUCTURE.md (technical reference)
├── PREPARATION.md (instructor setup)
│
├── exercise_0_project_setup/
│   └── INSTRUCTIONS.md
│
├── exercise_1_raw_data/
│   ├── INSTRUCTIONS.md
│   └── raw_data/
│       ├── wellbeing.tsv
│       ├── wellbeing.xlsx
│       └── fitness_data.tsv
│
├── exercise_2_hunting_errors/
│   ├── INSTRUCTIONS.md
│   └── bad_examples/ (13 files with errors)
│
├── exercise_2_participant_mapping/
│   ├── INSTRUCTIONS.md
│   └── raw_data/ (same wellbeing files)
│
├── exercise_3_using_recipes/
│   ├── INSTRUCTIONS.md
│   └── recipe-wellbeing.json
│
└── exercise_4_templates/
    ├── INSTRUCTIONS.md
    └── survey-wellbeing.json
```

---

## ✅ Success Criteria

By the end of this workshop, you will be able to:
- ✅ Create a YODA-structured research project
- ✅ Convert raw survey data to BIDS/PRISM format
- ✅ Identify and fix data quality issues
- ✅ Transform demographic data with custom encodings
- ✅ Automatically score assessments using recipes
- ✅ Create reusable metadata templates
- ✅ Export analysis-ready data to standard formats (SPSS, CSV)
- ✅ Understand the complete PRISM validation pipeline

---

## 🤝 Questions or Issues?

- Check [STRUCTURE.md](STRUCTURE.md) for technical details
- See [PREPARATION.md](PREPARATION.md) for instructor resources
- Consult the error code documentation in `../../docs/ERROR_CODES.md`
- Open an issue on the PRISM GitHub repository
