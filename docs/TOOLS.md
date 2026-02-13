# Tools

Advanced tools available in PRISM Studio's Tools dropdown menu.

```{note}
This page is under construction. For now, see [Studio Overview](STUDIO_OVERVIEW.md) for an overview of all tools.
```

## File Management

### Renamer by Example

Quickly rename files to PRISM/BIDS format using pattern matching.

**How it works**:
1. Provide an example of your current naming: `participant_001_task.tsv`
2. Show the desired BIDS name: `sub-001_task-depression_survey.tsv`
3. PRISM extracts the pattern and applies it to all similar files

**Example patterns**:
- `P001_baseline` → `sub-001_ses-baseline`
- `subj-1_anxiety.csv` → `sub-001_task-anxiety_survey.tsv`

### Folder Organizer

Organize flat file lists into BIDS directory structure.

**Input** (flat folder):
```
sub-001_task-depression_survey.tsv
sub-001_task-anxiety_survey.tsv
sub-002_task-depression_survey.tsv
```

**Output** (BIDS structure):
```
sub-001/survey/sub-001_task-depression_survey.tsv
sub-001/survey/sub-001_task-anxiety_survey.tsv
sub-002/survey/sub-002_task-depression_survey.tsv
```

## Survey & Boilerplate

### Survey Generator

Create new survey files from scratch or templates.

**Options**:
- Start from blank
- Copy from library
- Generate from structure file

### Survey Customizer

Modify existing surveys:
- Add/remove items
- Edit question text
- Update response options
- Add translations (EN/DE)

### Library Browser

Browse the official PRISM survey library with 100+ validated instruments:
- WHO-5 Well-Being Index
- PHQ-9 Depression
- GAD-7 Anxiety
- Beck Depression Inventory
- And many more...

## Recipes & Scoring

### What Are Recipes?

Recipes define how to calculate scores from raw survey data:

```json
{
  "RecipeName": "PHQ-9 Total Score",
  "Scoring": {
    "PHQ9_total": {
      "operation": "sum",
      "items": ["PHQ01", "PHQ02", "...", "PHQ09"]
    }
  }
}
```

### Running Recipes

1. Go to **Tools → Recipes & Scoring**
2. Select your dataset
3. Choose recipes from the library or your project
4. Click **Run**
5. Export results as SPSS or CSV

### Export Formats

| Format | Extension | Features |
|--------|-----------|----------|
| SPSS | `.save` | Variable labels, value labels |
| CSV | `.csv` | Universal compatibility |
| TSV | `.tsv` | BIDS-compatible |

→ See [Recipes Guide](RECIPES.md) for creating custom recipes.

## Template Editor

Create and edit survey/biometrics metadata templates.

### Features

- **Form-based editing**: No raw JSON required
- **Schema validation**: Ensures templates are valid
- **Bilingual support**: German and English text
- **Library integration**: Start from official templates

### Creating a Template

1. Go to **Tools → Template Editor**
2. Select modality (Survey, Biometrics)
3. Add general information
4. Add items with:
   - Item ID (column name)
   - Question text (EN/DE)
   - Response options
5. Save to project or download

## JSON Editor (Advanced)

Direct JSON editing for power users:
- Syntax highlighting
- Schema validation
- Auto-completion

Use this for:
- Bulk editing
- Complex nested structures
- Debugging

## AND Export

Export PRISM datasets to AND (Austrian NeuroCloud) compatible format.

### What It Does

Converts your PRISM dataset into a submission-ready package for AND with:
- **README.md** in AND structure (overview, methods, missing data)
- **CITATION.cff** with proper dataset citation metadata
- **.bids-validator-config.json** for PRISM-specific validation rules
- **Git LFS setup** (optional) if required by AND

### CLI Usage

```bash
# Basic export (DataLad-friendly)
python -m src.converters.anc_export /path/to/dataset

# With Git LFS conversion (if AND requires it)
python -m src.converters.anc_export /path/to/dataset --git-lfs

# With metadata
python -m src.converters.anc_export /path/to/dataset --metadata info.json
```

### What Gets Preserved

- ✅ All BIDS compatibility (existing tools still work)
- ✅ PRISM extensions (survey/, biometrics/)
- ✅ DataLad compatibility (default)
- ✅ Custom code/ and derivatives/

### DataLad vs Git LFS

**Default**: Stays DataLad-compatible  
**With `--git-lfs`**: Converts to Git LFS format for AND submission

**Important**: Check with AND whether they accept DataLad datasets before converting to Git LFS!

→ See [AND Export Guide](ANC_EXPORT.md) for detailed documentation.

---

## Quick Reference

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **Renamer** | Fix filenames | After importing data |
| **Organizer** | Create folders | After renaming files |
| **Survey Gen** | Create surveys | Starting new task |
| **Customizer** | Edit surveys | Adding translations |
| **Library** | Browse templates | Finding instruments |
| **Recipes** | Calculate scores | After data collection |
| **Template Ed** | Create metadata | Documenting data |
| **JSON Editor** | Raw editing | Advanced users |
| **AND Export** | Prepare for AND submission | Before sharing data |
