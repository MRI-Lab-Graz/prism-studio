# Workshop Exercise Structure - Quick Reference

## 📁 Complete Folder Organization

\`\`\`
demo/workshop/
│
├── WORKSHOP_README.md                     ← START HERE! Main entry point
├── README.md                              ← Technical notes for instructors
│
├── exercise_0_project_setup/              ← 10 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   └── INSTRUCTIONS.pdf
│
├── exercise_1_raw_data/                   ← 30 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   ├── INSTRUCTIONS.pdf
│   └── raw_data/
│       ├── wellbeing.tsv
│       └── fitness_data.tsv
│
├── exercise_2_hunting_errors/             ← 25 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   ├── INSTRUCTIONS.pdf
│   └── bad_examples/                      ← 13 messy files to investigate
│
├── exercise_3_using_recipes/              ← 20 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   └── INSTRUCTIONS.pdf
│
├── exercise_4_templates/                  ← 20 min
│   ├── INSTRUCTIONS.md                    ← Student instructions
│   └── INSTRUCTIONS.pdf
│
├── library/                               ← Templates & recipes
├── reference_solution/                    ← Complete example
└── recipes/                               ← Scoring recipes
\`\`\`

---

## 🎯 Exercise Flow

### For Students:

1. **Read first:** \`WORKSHOP_README.md\`
2. **Exercise 0:** \`exercise_0_project_setup/INSTRUCTIONS.md\`
3. **Exercise 1:** \`exercise_1_raw_data/INSTRUCTIONS.md\`
4. **Exercise 2:** \`exercise_2_hunting_errors/INSTRUCTIONS.md\`
5. **Exercise 3:** \`exercise_3_using_recipes/INSTRUCTIONS.md\`
6. **Exercise 4:** \`exercise_4_templates/INSTRUCTIONS.md\`

---

## 📝 Instruction Files Content

### Exercise 0: Project Setup
- Launching Prism.exe (Windows)
- Accessing http://localhost:5001/projects
- Creating a new PRISM project

### Exercise 1: Handling Raw Data
- GUI converter usage for survey and biometrics
- Column mapping (participant_id, session)
- Creating a PRISM dataset structure

### Exercise 2: Hunting for Errors
- Guided "Bug Hunt" in the \`bad_examples/\` folder
- Identification of common data issues
- Understanding Validator feedback

### Exercise 3: Using Recipes
- Automated scoring for Wellbeing and Fitness
- Exporting to SPSS (.sav) with full metadata
- Verifying automated calculations

### Exercise 4: Making & Editing Templates
- Using the JSON Template Editor
- Creating custom survey definitions from scratch
- Validating templates against PRISM schemas
