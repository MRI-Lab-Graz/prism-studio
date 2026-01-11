# PRISM Workshop: Structured Exercises

Welcome to the PRISM workshop! This folder contains three hands-on exercises to teach you the complete workflow from raw data to analysis-ready outputs.

## 📚 Workshop Structure

The workshop consists of three sequential exercises, each in its own folder:

```
workshop/
├── exercise_1_raw_to_bids/        ← Start here!
├── exercise_2_json_metadata/
├── exercise_3_recipes_export/
└── reference_solution/             ← Check your work
```

---

## 🎯 Learning Path

### Exercise 1: Converting Raw Data to BIDS Structure
**⏱️ Time:** 30 minutes  
**📁 Location:** `exercise_1_raw_to_bids/`

**You'll learn:**
- BIDS folder hierarchy
- File naming conventions
- Using the GUI converter
- Understanding sidecar files

**Start here:** Open `exercise_1_raw_to_bids/INSTRUCTIONS.md`

---

### Exercise 2: Creating & Editing JSON Metadata
**⏱️ Time:** 25 minutes  
**📁 Location:** `exercise_2_json_metadata/`

**You'll learn:**
- JSON structure for metadata
- Adding survey descriptions
- Creating value labels
- Using library templates

**Prerequisites:** Complete Exercise 1 first

**Start here:** Open `exercise_2_json_metadata/INSTRUCTIONS.md`

---

### Exercise 3: Recipes & SPSS Export
**⏱️ Time:** 20 minutes  
**📁 Location:** `exercise_3_recipes_export/`

**You'll learn:**
- Automated scoring with recipes
- Exporting to SPSS format
- Generating codebooks
- Creating methods text

**Prerequisites:** Complete Exercises 1 & 2 first

**Start here:** Open `exercise_3_recipes_export/INSTRUCTIONS.md`

---

## 🚀 Getting Started

### 1. Launch PRISM Studio
```bash
# Navigate to PRISM directory
cd /path/to/psycho-validator

# Activate virtual environment
source .venv/bin/activate    # macOS/Linux
# or
.\.venv\Scripts\activate     # Windows

# Start the server
python prism-studio.py
```

Open browser to: **http://localhost:5001**

### 2. Open Exercise 1 Instructions
Navigate to `exercise_1_raw_to_bids/INSTRUCTIONS.md` and follow along!

---

## 📋 Workshop Materials

### Raw Data (Exercise 1)
- `exercise_1_raw_to_bids/raw_data/phq9_scores.tsv` - Depression questionnaire responses (tab-delimited with `phq9_01`-style columns)
- `exercise_1_raw_to_bids/raw_data/participants_raw.tsv` - Demographics

### Templates & Recipes
Available in the workshop folder:
- `library/survey/survey-phq9.json` - PHQ-9 metadata template (for Exercise 2)
- `demo/workshop/recipes/surveys/phq9.json` - PHQ-9 scoring recipe (used in Exercise 3)

**Note:** The recipe lives in `demo/workshop/recipes/surveys/phq9.json`; just pick "phq9" from the GUI dropdown.

### Reference Solution
- `reference_solution/` - Complete, valid dataset to compare your work

---

## 🎓 Learning Objectives

By the end of this workshop, you will be able to:

✅ Convert unstructured CSV files to BIDS format  
✅ Create proper JSON metadata (sidecars)  
✅ Understand BIDS naming conventions  
✅ Fill in survey descriptions and value labels  
✅ Use the library system for templates  
✅ Apply recipes for automated scoring  
✅ Export analysis-ready data to SPSS  
✅ Generate codebooks and methods text  

---

## 📊 What You'll Create

Starting with simple CSV files, you'll create:

```
my_dataset/                              ← Your BIDS dataset
├── dataset_description.json
├── participants.tsv
├── sub-01/
│   └── ses-01/
│       └── survey/
│           ├── sub-01_ses-01_task-phq9_survey.tsv
│           └── sub-01_ses-01_task-phq9_survey.json  ← Rich metadata!
└── recipes/
    └── surveys/
        └── phq9/
            ├── phq9.sav                 ← SPSS file with labels!
            ├── phq9_codebook.json
            └── methods_boilerplate.md   ← Auto-generated methods!
```

---

## 💡 Tips for Success

### Take Your Time
- Read each instruction carefully
- Don't skip validation steps
- Ask questions if something is unclear

### Use the GUI
- All tasks can be done through the web interface
- No command line required!
- Screenshots in instructions show you where to click

### Save Your Work
- Your dataset from Exercise 1 is used in Exercises 2 & 3
- Don't delete or move files between exercises
- Keep a backup if you want to start over

### Check the Reference
- Compare your work to `reference_solution/`
- If validation fails, check what's different
- It's OK to peek at the solution!

---

## 🆘 Getting Help

### During the Workshop
- Raise your hand for the instructor
- Check with your neighbor
- Look at `reference_solution/` for comparison

### Common Issues
Each exercise has a **Troubleshooting** section at the bottom:
- Check there first for common problems
- Solutions are provided for typical errors

### After the Workshop
- Full documentation in `docs/` folder
- GitHub Issues for bug reports
- Community discussions for questions

---

## 📖 Additional Resources

### Workshop Documentation
- `docs/WORKSHOP_PLAN.md` - Overall workshop strategy (for instructors)
- `docs/WORKSHOP_HANDOUT.md` - Complete reference guide
- `docs/README.md` - Technical details about demo data

### PRISM Documentation
- `docs/QUICK_START.md` - Getting started with PRISM
- `docs/SPECIFICATIONS.md` - Technical specifications
- `docs/RECIPES.md` - Recipe system documentation
- `docs/WEB_INTERFACE.md` - GUI guide

### Example Data
- `demo/prism_demo/` - Complete example dataset
- `demo/comprehensive_demo_dataset/` - Multi-modal examples
- `library/` - Template collection

---

## ⏱️ Time Management

**Total workshop time: ~90 minutes (without breaks)**

- Exercise 1: 30 min
- Exercise 2: 25 min
- Exercise 3: 20 min
- Buffer: 15 min (Q&A, troubleshooting)

**With a 10-minute break:**
- Total: 100 minutes (~1h 40m)
- Perfect for a 2-hour session with intro/wrap-up

---

## 🎯 Success Criteria

You've successfully completed the workshop when:

1. **Exercise 1 Complete:**
   - [ ] Created a BIDS-structured dataset
   - [ ] Files follow naming conventions
   - [ ] Basic validation passes (structure OK)

2. **Exercise 2 Complete:**
   - [ ] All JSON sidecars have complete metadata
   - [ ] Value labels (Levels) are defined
   - [ ] Full validation passes (no warnings)

3. **Exercise 3 Complete:**
   - [ ] Recipe ran successfully
   - [ ] SPSS file created with labels
   - [ ] Data opens in SPSS/Jamovi
   - [ ] Methods text generated

---

## 🌟 Next Steps After the Workshop

### Apply to Your Own Data
1. Start with a small dataset (5-10 participants)
2. Use one familiar instrument
3. Follow the same three-step workflow

### Build Your Library
1. Create templates for your common surveys
2. Save them to `library/` for reuse
3. Share with your lab/collaborators

### Create Custom Recipes
1. Look at existing recipes as examples
2. Write recipes for your instruments
3. Test thoroughly with known data

### Get Involved
- ⭐ Star the project on GitHub
- 🐛 Report bugs you find
- 💡 Suggest improvements
- 📚 Contribute templates to the community

---

## 📧 Contact & Feedback

**Instructor Contact:** [to be provided]

**Feedback:** We'd love to hear your thoughts!
- What worked well?
- What was confusing?
- What should we add/change?

Please share your feedback with the instructor or via GitHub Issues.

---

## 📜 License & Citation

PRISM is open-source software. If you use it in your research, please cite:

[Citation information will be provided by instructor]

---

**Ready to start?** 🚀

👉 **Go to: `exercise_1_raw_to_bids/INSTRUCTIONS.md`**

Good luck and enjoy the workshop! 🎉
