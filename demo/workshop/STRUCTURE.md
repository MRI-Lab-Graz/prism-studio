# Workshop Exercise Structure - Quick Reference

## 📁 Complete Folder Organization

```
demo/workshop/
│
├── WORKSHOP_README.md                     ← START HERE! Main entry point
├── README.md                              ← Technical notes for instructors
│
├── exercise_1_raw_to_bids/                ← 30 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   ├── raw_data/
│   │   ├── phq9_scores.tsv               ← PHQ-9 responses (tab-delimited with `phq9_01` columns)
│   │   └── participants_raw.tsv           ← Demographics
│   └── my_dataset/                        ← Students create this
│       └── (BIDS structure created here)
│
├── exercise_2_json_metadata/              ← 25 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   └── starter_dataset/                   ← Optional: pre-made dataset
│       └── (if students need to skip Ex 1)
│
├── exercise_3_recipes_export/             ← 20 min
│   └── INSTRUCTIONS.md                    ← Student instructions
│
├── library/                     ← Templates & recipes
│   ├── README.md                          ← Usage instructions
│   ├── survey/                            ← Survey templates
│   │   └── survey-phq9.json               ← Metadata template (Ex 2)
│   └── biometrics/                        ← Biometric templates (future)
│
├── reference_solution/                    ← Complete example
│   └── (fully valid BIDS dataset)
│
├── messy_dataset/                         ← Legacy (optional)
│   └── (from old workshop version)
│
└── raw_material/                          ← Original files (backup)
    ├── phq9_scores.csv
    └── participants_raw.csv
```

---

## 🎯 Exercise Flow

### For Students:

1. **Read first:** `WORKSHOP_README.md`
2. **Exercise 1:** `exercise_1_raw_to_bids/INSTRUCTIONS.md`
3. **Exercise 2:** `exercise_2_json_metadata/INSTRUCTIONS.md`
4. **Exercise 3:** `exercise_3_recipes_export/INSTRUCTIONS.md`
5. **Compare:** Check your work against `reference_solution/`

### For Instructors:

1. **Preparation:** Read `README.md` (instructor notes)
2. **Planning:** Review `docs/WORKSHOP_PLAN.md`
3. **Reference:** Keep `docs/WORKSHOP_HANDOUT.md` handy

---

## 📝 Instruction Files Content

### Exercise 1: INSTRUCTIONS.md
- Step-by-step GUI converter usage
- Column mapping instructions
- File structure explanation
- Validation checkpoint
- Troubleshooting section
- ~30 minutes to complete

### Exercise 2: INSTRUCTIONS.md
- JSON editor usage
- Metadata hierarchy explanation
- PHQ-9 item descriptions (all 9 items)
- Value labels (Levels) definition
- Library template usage
- Validation checkpoint
- ~25 minutes to complete

### Exercise 3: INSTRUCTIONS.md
- Recipe configuration
- SPSS export settings
- Result verification in SPSS
- Codebook review
- Methods text generation
- Excel export alternative
- ~20 minutes to complete

---
-- Templates exist in `library/` (`survey-phq9.json`)
-- [ ] Recipe is ready in `demo/workshop/recipes/surveys/phq9.json`

### Before Workshop:
- [ ] Raw data files exist in `exercise_1_raw_to_bids/raw_data/`
- [ ] `library/survey/survey-phq9.json` template exists
- [ ] `demo/workshop/recipes/surveys/phq9.json` recipe exists
- [ ] `reference_solution/` is complete and validated
- [ ] PRISM Studio launches successfully
- [ ] Test run through all three exercises (90 min)

### During Workshop:
- [ ] Share link to `WORKSHOP_README.md` with students
- [ ] Monitor progress through exercises
- [ ] Help with troubleshooting
- [ ] Answer questions about concepts

### After Workshop:
- [ ] Collect feedback
- [ ] Update instructions based on common questions
- [ ] Reset demo folders for next session

---

## 🚀 Quick Start Command

For students to launch:
```bash
cd /path/to/psycho-validator
source .venv/bin/activate
python prism-studio.py
```

Then open browser to: **http://localhost:5001**

---

## 📊 Expected Outcomes

### After Exercise 1:
```
exercise_1_raw_to_bids/my_dataset/
├── dataset_description.json
├── participants.tsv
└── sub-01/ses-01/survey/
    ├── sub-01_ses-01_task-phq9_survey.tsv
    └── sub-01_ses-01_task-phq9_survey.json  (basic)
```

### After Exercise 2:
- Same structure, but JSON files now have:
  - Complete `General` section
  - Complete `Technical` section
  - All 9 items with `Description` and `Levels`

### After Exercise 3:
```
exercise_1_raw_to_bids/my_dataset/recipes/surveys/phq9/
├── phq9.sav                     (SPSS file)
├── phq9_codebook.json
├── phq9_codebook.tsv
└── methods_boilerplate.md
```

---

## 💾 File Sizes (Approximate)

- Raw CSVs: ~2-5 KB each
- Each TSV data file: ~1 KB
- Each JSON sidecar: ~3-5 KB (basic) → ~15-20 KB (complete)
- SPSS .sav file: ~5-10 KB
- Total dataset: ~100-200 KB (for 10-15 participants)

---

## 🔧 Troubleshooting Quick Reference

### "Can't find raw data"
→ Check `exercise_1_raw_to_bids/raw_data/`

### "Converter not working"
→ Make sure PRISM Studio is running on port 5001

### "Validation fails"
→ Check file naming (needs hyphens: `sub-01` not `sub01`)

### "Recipe not found"
→ Verify `recipes/surveys/phq9.json` exists

### "SPSS file has no labels"
→ Ensure JSON sidecars have `Levels` defined

---

## 📚 Related Documentation

- `docs/WORKSHOP_PLAN.md` - Overall strategy & timing
- `docs/WORKSHOP_HANDOUT.md` - Complete reference guide
- `docs/QUICK_START.md` - General PRISM guide
- `docs/RECIPES.md` - Recipe system documentation

---

**Last Updated:** 2026-01-11  
**Workshop Version:** 2.0 (GUI-focused, modular exercises)
