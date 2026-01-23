# PRISM Studio Overview

PRISM Studio is the web-based interface for PRISM. It provides a user-friendly way to manage projects, convert data, validate datasets, and run scoring recipes.

## Launching PRISM Studio

```bash
python prism-studio.py
```

Your browser opens to `http://localhost:5001`. If it doesn't open automatically, navigate there manually.

---

## Navigation

The main navigation bar provides access to all features:

| Tab | Purpose |
|-----|---------|
| **Home** | Quick actions and recent projects |
| **Projects** | Create, open, and manage projects |
| **Validator** | Validate datasets against PRISM/BIDS |
| **Converter** | Import data from Excel, CSV, SPSS |
| **Tools** | Advanced features (see below) |
| **Specs** | View PRISM specifications |
| **Docs** | Link to this documentation |

### Tools Dropdown

| Tool | Description |
|------|-------------|
| **File Management** | Rename files, organize into folders |
| **Survey & Boilerplate** | Generate survey files, browse library |
| **Recipes & Scoring** | Calculate questionnaire scores, export SPSS |
| **Template Editor** | Create/edit survey metadata templates |
| **JSON Editor** | Advanced manual JSON editing |

---

## Home Page

The home page shows:

1. **Current Project** – The active project (if loaded)
2. **Quick Actions** – Common tasks
3. **Recent Projects** – Previously opened projects
4. **Getting Started** – Links to documentation and workshop

---

## Projects Page

### Create New Project

Creates a YODA-structured project:

```
project_name/
├── rawdata/           ← PRISM validates here
│   ├── dataset_description.json
│   └── participants.tsv
├── code/              ← Your analysis scripts
├── analysis/          ← Results and derivatives
├── project.json       ← Project metadata
├── contributors.json  ← Team information
└── CITATION.cff       ← Citation file
```

**Fields**:
- **Project Name**: Folder name (no spaces, use underscores)
- **Project Location**: Parent directory

### Open Existing Project

Load a project by selecting its `project.json` file or the project folder.

**Recent Projects**: Click any recent project to quickly reopen it.

### Project Metadata

Once a project is loaded, you can edit:

- **Dataset Description** – Name, authors, license
- **Participants** – Demographic variables, NeuroBagel compliance
- **Settings** – Library paths, default modalities

---

## Validator Page

### Running Validation

1. Your project's `rawdata/` folder is pre-selected
2. Click **Validate**
3. Wait for results (progress shown)

### Understanding Results

Results are grouped by severity:

| Icon | Level | Meaning |
|------|-------|---------|
| ❌ | Error | Must fix – dataset is invalid |
| ⚠️ | Warning | Should fix – may cause issues |
| 💡 | Suggestion | Could improve – best practices |

### Result Details

Click any issue to see:
- **File path** – Which file has the problem
- **Error code** – e.g., PRISM101
- **Description** – What's wrong
- **How to fix** – Suggested solution

### Auto-Fix

Some issues can be fixed automatically:
1. Click the **Auto-Fix** button on fixable issues
2. Review the proposed changes
3. Apply fixes

### BIDS Validation

Toggle **Include BIDS Validation** to also run the standard BIDS validator. This checks MRI-specific requirements.

---

## Converter Page

### Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| Excel | `.xlsx`, `.xls` | Multiple sheets supported |
| CSV | `.csv` | Comma-separated |
| TSV | `.tsv` | Tab-separated |
| SPSS | `.sav` | With value labels |
| LimeSurvey | `.csv` | Special handling for LS exports |

### Conversion Workflow

1. **Select Source File** – Browse or drag-and-drop
2. **Preview Data** – Check columns and rows
3. **Map Columns**:
   - Select the participant ID column
   - Choose which columns to include
   - Set the task name
4. **Convert** – Generate PRISM-formatted files
5. **Save to Project** – Copy files to your `rawdata/` folder

### Participants Mapping

For demographic data with custom encodings:

1. Click **Participants Mapping**
2. Define transformation rules
3. Apply to generate standardized `participants.tsv`

See [Participants Mapping](PARTICIPANTS_MAPPING.md) for details.

---

## Tools

### File Management

**Renamer by Example**: Quickly rename files to PRISM/BIDS format.
- Enter an example: `participant_001_task.tsv` → `sub-001_task-depression_survey.tsv`
- Apply the pattern to all similar files

**Folder Organizer**: Move flat files into subject/session/modality folders.

### Survey & Boilerplate

**Survey Generator**: Create survey files from scratch or templates.

**Survey Customizer**: Modify existing surveys:
- Add/remove items
- Edit response options
- Update translations

**Library Browser**: Browse the official PRISM survey library with 100+ validated instruments.

### Recipes & Scoring

**Recipe Runner**:
1. Select your dataset
2. Choose recipes (scoring algorithms)
3. Run to calculate scores
4. Export as SPSS (.sav) or CSV

**Recipe Features**:
- Sum scores, mean scores, reverse coding
- Conditional scoring (subscales)
- Custom formulas
- Value labels for SPSS

### Template Editor

Create and edit survey/biometrics metadata templates:

- **Items**: Questions, response options
- **Bilingual**: German and English text
- **Schema Validation**: Ensures templates are valid

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + S` | Save current file |
| `Ctrl/Cmd + O` | Open project |
| `Ctrl/Cmd + V` | Run validation |

---

## Quitting PRISM Studio

Click **Quit** in the navigation bar (red X icon) to:
1. Save any unsaved changes
2. Shut down the web server
3. Close the application

Or press `Ctrl+C` in the terminal where PRISM Studio is running.

---

## Next Steps

- **[Projects](PROJECTS.md)** – Detailed project management guide
- **[Converter](CONVERTER.md)** – Data conversion reference
- **[Validator](VALIDATOR.md)** – Validation deep-dive
- **[Workshop](WORKSHOP.md)** – Hands-on exercises
