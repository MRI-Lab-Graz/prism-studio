# Workshop Structure & Technical Reference

This document provides technical details about the workshop organization and file structure.

---

## 📁 Complete Folder Organization

```
examples/workshop/
│
├── README.md                              ← START HERE! Overview & quick start
├── STRUCTURE.md                           ← This file (technical reference)
├── PREPARATION.md                         ← Instructor setup & facilitation guide
│
├── exercise_0_project_setup/
│   ├── INSTRUCTIONS.md                    ← Create YODA project structure
│   └── (student creates project folder here)
│
├── exercise_1_raw_data/
│   ├── INSTRUCTIONS.md                    ← Convert raw data to BIDS/PRISM
│   ├── raw_data/
│   │   ├── wellbeing.tsv                  ← Tab-separated survey data (9 participants)
│   │   ├── wellbeing.xlsx                 ← Same data in Excel format
│   │   └── fitness_data.tsv               ← Optional bonus biometrics data
│   └── (students create my_dataset/ here)
│
├── exercise_2_hunting_errors/
│   ├── INSTRUCTIONS.md                    ← Learn data validation & error detection
│   └── bad_examples/
│       ├── bad_01.tsv through bad_13.tsv  ← 13 files with intentional errors
│       └── (for students to investigate)
│
├── exercise_2_participant_mapping/
│   ├── INSTRUCTIONS.md                    ← Create mapping specifications
│   ├── raw_data/                          ← (symlinked to exercise 1)
│   └── (students create participants_mapping.json here)
│
├── exercise_3_using_recipes/
│   ├── INSTRUCTIONS.md                    ← Apply scoring recipes
│   └── recipe-wellbeing.json              ← Pre-made recipe for WHO-5 scoring
│
├── exercise_4_templates/
│   ├── INSTRUCTIONS.md                    ← Create metadata templates
│   └── survey-wellbeing.json              ← Reference WHO-5 template from official library
│
└── (optional materials)
    ├── PREPARATION.md                     ← Instructor guide
    └── solutions/                         ← Example solutions (if available)
```

---

## ⏱ Exercise Durations & Structure

| # | Exercise | Duration | Concepts | Dependencies |
|---|----------|----------|----------|--------------|
| **0** | Project Setup | 15 min | YODA structure, project organization | None |
| **1** | Raw Data Import | 30 min | BIDS naming, file format conversion | Exercise 0 |
| **2** | Error Hunting | 25 min | Data validation, error types | Exercise 1 |
| **3** | Participant Mapping | 45 min | Encoding, standardization, JSON | Exercise 1 |
| **4** | Using Recipes | 20 min | Automated scoring, SPSS export | Exercise 1 |
| **5** | Creating Templates | 20 min | Metadata, documentation, reusability | Exercise 1 & 4 |

**Total: ~2 hours** (or ~2.5 hours with breaks)

**Minimum viable workshop:** Exercises 0-3 (~75 minutes)

---

## 📊 Data Used in Workshop

### WHO-5 Well-Being Index

**Instrument:**
- 5-item self-report questionnaire
- Measures overall psychological well-being
- 0-5 Likert scale per item (0=worst, 5=best)
- Total score range: 5-25
- Widely used in clinical research and practice

**Items:**
- WB01: Cheerful and in good spirits
- WB02: Calm and relaxed
- WB03: Active and vigorous
- WB04: Fresh and rested (wake up)
- WB05: Daily life filled with interesting things

**Demographics collected:**
- participant_id (DEMO001-DEMO009)
- age (22-52 years)
- sex (1=M, 2=F, 4=Other)
- education (1-6 scale)
- handedness (1=R, 2=L)
- completion_date

### Source Data Files

- **wellbeing.tsv**: 10 rows (1 header + 9 data rows), 11 columns
- **wellbeing.xlsx**: Same data in Excel format
- **fitness_data.tsv**: Optional bonus data for extended learning

All files are in `exercise_1_raw_data/raw_data/` directory.

---

## 🔄 Workflow Progression

```
┌─────────────────────────────────────┐
│ Exercise 0: Project Setup           │  ← Create YODA folder structure
├─────────────────────────────────────┤
│ wellbeing.xlsx (raw Excel file)     │  ← Starting material
├─────────────────────────────────────┤
│ Exercise 1: Data Conversion         │  ← Convert to BIDS format
├─────────────────────────────────────┤
│ my_dataset/ (BIDS-formatted data)   │  ← Created by conversion
├─────────────────────────────────────┤
│ Exercise 2: Error Hunting           │  ← Learn validation
├─────────────────────────────────────┤
│ Exercise 3: Participant Mapping     │  ← Standardize demographics
├─────────────────────────────────────┤
│ participants_mapping.json (created) │  ← Mapping specification
├─────────────────────────────────────┤
│ Exercise 4: Using Recipes           │  ← Calculate scores
├─────────────────────────────────────┤
│ wellbeing_scores.csv/.sav (created) │  ← Scored data for analysis
├─────────────────────────────────────┤
│ Exercise 5: Creating Templates      │  ← Create documentation
├─────────────────────────────────────┤
│ survey-wellbeing.json (template)    │  ← Reusable metadata
└─────────────────────────────────────┘
         ↓
    PUBLICATION-READY DATASET
    WITH FULL DOCUMENTATION
```

---

## 🎯 Learning Objectives by Exercise

### Exercise 0: Project Setup
**Students will:**
- Understand YODA principles and benefits
- Create a reproducible project structure
- Activate a project in PRISM
- Know why organization matters

**Key Files:**
- INSTRUCTIONS.md: YODA concepts, step-by-step walkthrough

---

### Exercise 1: Raw Data Import
**Students will:**
- Understand BIDS file naming conventions
- Use PRISM's Data Converter GUI
- Map columns correctly
- Create properly structured dataset
- Generate JSON sidecars

**Key Files:**
- wellbeing.tsv: Raw survey data
- INSTRUCTIONS.md: Detailed conversion guide
- Output: `my_dataset/` (BIDS-structured)

---

### Exercise 2: Error Hunting
**Students will:**
- Identify common data quality issues
- Use PRISM Validator
- Understand Error vs. Warning vs. Info messages
- Learn to read validation reports
- Know how to fix problems

**Key Files:**
- bad_examples/: 13 files with intentional errors
- INSTRUCTIONS.md: Investigation guide
- No output files (analysis-focused exercise)

---

### Exercise 3: Participant Mapping
**Students will:**
- Understand why encoding standardization matters
- Create `participants_mapping.json`
- Document custom variable encodings
- Apply automated transformations
- Generate standardized participants.tsv

**Key Files:**
- INSTRUCTIONS.md: Mapping specification guide
- participants_mapping.json: Template specification file
- Output: standardized participants.tsv

---

### Exercise 4: Using Recipes
**Students will:**
- Understand recipe structure and benefits
- Apply scoring recipes to data
- Calculate total scores automatically
- Export to SPSS format
- Generate codebooks

**Key Files:**
- recipe-wellbeing.json: WHO-5 scoring recipe
- INSTRUCTIONS.md: Recipe application guide
- Output: wellbeing_scores.csv/.sav, codebook

---

### Exercise 5: Creating Templates
**Students will:**
- Understand metadata templates
- Create survey documentation in JSON
- Validate templates
- Reuse templates across datasets
- Understand BIDS schema

**Key Files:**
- official/library/survey/survey-wellbeing.json: Reference template
- INSTRUCTIONS.md: Template creation guide
- Output: survey-wellbeing-workshop.json (custom template)

---

## 🛠 Tools & Technologies

### Required Software
- **Python 3.9+** (activate with `source .venv/bin/activate`)
- **PRISM Studio** (run with `python prism-studio.py`)
- **Web Browser** (Chrome, Firefox, Safari, or Edge)
- **Text Editor** (for viewing/editing JSON files)

### Optional Software
- **SPSS** or **Jamovi** (to open .sav files)
- **Excel/Sheets** (to view .csv files)
- **VS Code** (recommended text editor with JSON syntax highlighting)

### PRISM Features Used
- Data Converter (Exercise 1)
- Validator (Exercise 2)
- Participant Mapper (Exercise 3)
- Recipe Scorer (Exercise 4)
- Template Editor (Exercise 5)

---

## 📋 File Formats in Workshop

### TSV (Tab-Separated Values)
- Plain text format
- Columns separated by tabs
- Rows separated by newlines
- Readable in any text editor or spreadsheet
- Example: `wellbeing.tsv`

### JSON (JavaScript Object Notation)
- Structured data format
- Key-value pairs
- Hierarchical structure with objects and arrays
- Machine-readable and human-readable
- Examples: `participants_mapping.json`, `recipe-wellbeing.json`, `survey-wellbeing.json`

### SPSS .SAV
- Binary format for SPSS/Jamovi
- Contains data + metadata (value labels, variable descriptions)
- Export target from recipe scorer
- Example: `wellbeing_scores.sav`

### CSV (Comma-Separated Values)
- Plain text format
- Columns separated by commas
- Portable across all programs
- Example: `wellbeing_scores.csv`

### XLSX (Excel)
- Microsoft Excel format
- Contains formatting, formulas, sheets
- Example: `wellbeing.xlsx`

---

## 🔑 Key Concepts Introduced

### YODA Principles
- sourcedata/ (original files, read-only)
- rawdata/ (standardized format)
- code/ (analysis scripts)
- derivatives/ (outputs, scores)

### BIDS (Brain Imaging Data Structure)
- Hierarchical folder structure
- Standardized file naming
- Entity-key pairs: sub-, ses-, task-
- JSON sidecars for metadata

### Validation
- Error: Critical issues preventing processing
- Warning: Suspicious values worth checking
- Info: Informational messages

### Mapping/Encoding
- Transform custom codes to standard values
- Document through JSON specification
- Automate with mapping files
- Enable data integration across sites

### Recipes
- JSON files defining scoring logic
- Can sum, average, reverse-code items
- Generate codebooks automatically
- Enable reproducible scoring

### Templates
- Document instruments completely
- Include item descriptions, scales, interpretations
- Reusable across projects
- Enable sharing and archiving

---

## 💾 File Management During Workshop

### Files Created by Students

**Exercise 0:**
- A new folder: `Wellbeing_Study_Workshop/`
- With subfolders: sourcedata/, rawdata/, code/, derivatives/

**Exercise 1:**
- `my_dataset/` folder structure (BIDS-formatted)
- Multiple `.tsv` and `.json` files

**Exercise 3:**
- `participants_mapping.json` (mapping specification)
- Updated `participants.tsv` (standardized)

**Exercise 4:**
- `wellbeing_scores.csv` (scored data)
- `wellbeing_scores.sav` (for SPSS)
- `wellbeing_codebook.pdf` (documentation)

**Exercise 5:**
- `survey-wellbeing-workshop.json` (metadata template)

### Files Provided by Workshop
- `wellbeing.tsv`, `wellbeing.xlsx` (raw data)
- 13 bad example files (error examples)
- `recipe-wellbeing.json` (scoring recipe)
- `survey-wellbeing.json` (reference template)

### Directory Cleanup Tips
- Each exercise is independent (can delete previous exercise folders if needed)
- Keep `rawdata/` and `derivatives/` folders
- Recommended: Keep the final scored dataset and metadata

---

## 🏫 Classroom Facilitation Notes

### Setup Before Workshop
1. Test PRISM Studio on your system
2. Have workshop folder downloaded/prepared
3. Test file paths work on your operating system
4. Consider pre-creation of YODA project (optional)

### During Exercises
- Exercises 0-3: Students work individually on their computers
- Exercises 4-5: Can be done together on instructor's screen if time limited

### Troubleshooting
- **Port 5001 in use:** Change port in `prism-studio.py` config
- **File not found errors:** Check file paths match directory structure
- **Permission errors:** Ensure exercise folders are readable/writable
- **Encoding errors:** Most common with bad_examples/ - expected behavior!

---

## 📚 Additional Resources

### Inside Workshop Folder
- `README.md` - Main workshop overview
- `PREPARATION.md` - Instructor guide
- `official/library/survey/` - 100+ instrument templates
- `official/recipe/survey/` - Scoring recipes for many instruments

### In PRISM Documentation
- `docs/WEB_INTERFACE.md` - GUI reference
- `docs/CLI_REFERENCE.md` - Command-line usage
- `docs/RECIPES.md` - Recipe creation guide
- `docs/VALIDATOR.md` - Validation details
- `docs/SPECIFICATIONS.md` - BIDS/PRISM specs

### External Resources
- https://bids-standard.github.io/ - BIDS specification
- https://www.yoda-project.org/ - YODA principles
- https://psytoolkit.org/ - Instrument library

---

## ❓ FAQ

**Q: Can exercises be done out of order?**  
A: Exercises 0-3 must be sequential. Exercises 4-5 can be demoed while following 0-3.

**Q: How long does the workshop take?**  
A: ~2-2.5 hours for all exercises, or ~1.5 hours for Exercises 0-3 only.

**Q: Can students use their own data?**  
A: Yes! After completing the workshop with WHO-5 data, students can repeat with their own survey.

**Q: Is SPSS required?**  
A: No. Jamovi (free) or R can read the generated files. CSV format works in any program.

**Q: What if students want to deepen learning?**  
A: Recommend: creating own recipe, using official library templates, multi-language template creation.

---

## 🎯 Success Indicators

After completing this workshop, students should:
- ✅ Understand why data structure matters
- ✅ Know BIDS naming conventions
- ✅ Use PRISM tools confidently
- ✅ Validate their own data
- ✅ Create reusable documentation
- ✅ Explain steps to collaborators
- ✅ Handle common data problems

---

## 🚀 Next Steps for Instructors

- Prepare PREPARATION.md materials
- Test all filespath on your OS (Windows/Mac/Linux differences)
- Create student handouts if needed
- Plan timing based on your audience
- Consider pre-workshop setup if students are unfamiliar with CLI
- Plan post-workshop follow-up (apply to own data)
