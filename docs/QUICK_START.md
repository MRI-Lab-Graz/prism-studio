# Quick Start

Create your first PRISM project in 10 minutes using PRISM Studio.

## Step 1: Launch PRISM Studio

```bash
cd prism-studio
python prism-studio.py
```

Your browser opens to `http://localhost:5001`. You'll see the home page with quick actions.

## Step 2: Create a New Project

1. Click **Projects** in the navigation bar
2. Select **Create New Project**
3. Enter your project details:
   - **Project Name**: `my_first_study` (no spaces)
   - **Project Location**: Choose a folder (e.g., `Documents`)
4. Click **Create Project**

This creates a [YODA-structured](https://handbook.datalad.org/en/latest/basics/101-127-yoda.html) project:

```
my_first_study/
├── rawdata/           ← Your data goes here
├── code/              ← Analysis scripts
├── analysis/          ← Results
├── project.json       ← Project metadata
└── CITATION.cff       ← Citation information
```

## Step 3: Add Your Data

### Option A: Use the Converter (Recommended)

1. Click **Converter** in the navigation
2. Select your source file (Excel, CSV, SPSS)
3. Map columns to participant IDs and variables
4. Click **Convert & Save to Project**

### Option B: Manual Import

Copy your data files to `my_first_study/rawdata/`:

```
rawdata/
├── dataset_description.json
├── participants.tsv
└── sub-001/
    └── survey/
        ├── sub-001_task-questionnaire_survey.tsv
        └── sub-001_task-questionnaire_survey.json
```

## Step 4: Validate Your Dataset

1. Click **Validator** in the navigation
2. Your project's `rawdata/` folder is pre-selected
3. Click **Validate**
4. Review results:
   - ✅ **Green**: Valid files
   - ⚠️ **Yellow**: Warnings (should fix)
   - ❌ **Red**: Errors (must fix)

### Understanding Validation Results

| Error Code | Meaning | How to Fix |
|------------|---------|------------|
| PRISM101 | Missing sidecar JSON | Create a `.json` file for your data |
| PRISM201 | Invalid filename | Rename to `sub-XXX_task-YYY_modality.ext` |
| PRISM301 | Missing required field | Add the field to your JSON sidecar |

Click any error to see detailed explanations and auto-fix suggestions.

## Step 5: Run Scoring Recipes

If you have survey data:

1. Go to **Tools → Recipes & Scoring**
2. Select your dataset
3. Choose recipes from the library (e.g., WHO-5 Well-Being)
4. Click **Run Recipes**
5. Export results as SPSS or CSV

## What's Next?

### Hands-On Workshop

For a complete learning experience with example data:

```bash
# Open the workshop folder
cd examples/workshop
```

The workshop basics track includes 4 exercises:
1. **Project Setup** – YODA principles
2. **Data Conversion** – Excel to PRISM format
3. **Metadata & Validation** – Find and fix missing metadata
4. **Recipes & Scoring** – Calculate questionnaire scores and export

Optional add-ons (if time allows):
- **Participant Mapping** – Demographic transformations
- **Templates** – Build reusable survey metadata

See [Workshop Guide](WORKSHOP.md) for details.

### Explore the Interface

- **[Projects](PROJECTS.md)** – Manage datasets and metadata
- **[Converter](CONVERTER.md)** – Import data from various formats
- **[Validator](VALIDATOR.md)** – Understand validation errors
- **[Tools](TOOLS.md)** – File management, templates, recipes

### Use the CLI

For batch processing and scripting:

```bash
# Validate from command line
python prism.py /path/to/rawdata

# Run all recipes
python prism_tools.py recipes survey --prism /path/to/project --format save
```

See [CLI Reference](CLI_REFERENCE.md) for all commands.

---

## Common First-Time Issues

### "No files found in dataset"

Make sure your data is in the `rawdata/` subfolder, not the project root.

### "Missing dataset_description.json"

Create this required file in `rawdata/`:

```json
{
  "Name": "My Study",
  "BIDSVersion": "1.9.0",
  "DatasetType": "raw"
}
```

### "Invalid filename pattern"

Files must follow BIDS naming:
```
sub-<ID>_[ses-<session>_]task-<task>_<modality>.<ext>
```

Examples:
- ✅ `sub-001_task-depression_survey.tsv`
- ✅ `sub-001_ses-01_task-anxiety_survey.tsv`
- ❌ `participant1_depression.tsv`

---

## Getting Help

- **Documentation**: You're reading it! Use the sidebar to navigate.
- **Workshop**: `examples/workshop/` has step-by-step exercises
- **GitHub Issues**: [Report bugs or request features](https://github.com/MRI-Lab-Graz/prism-studio/issues)
