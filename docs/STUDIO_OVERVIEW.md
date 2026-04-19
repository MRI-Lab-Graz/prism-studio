# PRISM Studio Overview

PRISM Studio is the frontend-first workflow for PRISM.

Use Studio when you want guided project setup, conversion, validation, and scoring in one place. Use CLI when you need automation or CI.

This page is a short overview. Use the detailed workflow pages for step-by-step written guidance. Use the companion videos for quick hands-on examples.

## Start Studio

If you still need setup help, start with [INSTALLATION.md](INSTALLATION.md).

From repository root:

```bash
python prism-studio.py
```

Open `http://localhost:5001` if your browser does not open automatically.

## Workflow Map

The recommended order is:

1. Create or open a project.
2. Import or convert data.
3. Run validation.
4. Fix issues and re-validate.
5. Run recipes and export outputs.

(projects-page)=
## 1) Create or Open a Project

UI path: `Projects`

Goal:
- Create a clean research project structure.
- Keep validation target and analysis outputs separated.

Expected structure:

```text
project_name/
|-- dataset_description.json
|-- participants.tsv
|-- README.md
|-- CITATION.cff
|-- project.json
|-- contributors.json
|-- sourcedata/
|-- derivatives/
`-- code/
```

## 2) Convert and Import Data

UI path: `Converter`

Goal:
- Convert source files (Excel/CSV/TSV/SPSS/LimeSurvey) into PRISM-compatible files.

Inputs:
- Source data file(s)
- Participant ID column
- Item/data column mapping

Output:
- Subject-level files in PRISM/BIDS-like folder structure.

Use the detailed import guides for the beginner workflow:

- Sociodemographics import: [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md)
- Survey import: [SURVEY_IMPORT.md](SURVEY_IMPORT.md)

Studio uses three explicit Sociodemographics cases:

- Case 1: Import file as source of truth
- Case 2: Modify existing project files
- Case 3: Safe merge from imported file

Choose the matching case before preview and save so you do not mix create, modify-existing, and merge workflows.

## 3) Validate the Dataset

UI path: `Validator`

Goal:
- Detect filename, sidecar, and schema issues.
- Optionally include BIDS validation.

Result levels:
- Error: must fix
- Warning: should fix
- Suggestion: recommended improvement

What to do next:

1. Open issue details.
2. Apply fixes manually or with auto-fix when available.
3. Re-run validation until blocking errors are gone.

## 4) Tools for Metadata and Scoring

UI path: `Tools`

Main tools:
- `Template Editor`: create and complete project-local templates.
- `JSON Editor`: edit sidecars and participant metadata.
- `Recipe Builder`: create scoring recipes.
- `File Management`: organize and rename files safely.

Detailed written guides:

- Template Editor: [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- Recipe Builder: [RECIPE_BUILDER.md](RECIPE_BUILDER.md)

## 5) Export and Report

After validation and scoring:
- Keep scored results in `derivatives/`.
- Use the Projects export area for shareable or anonymized outputs.
- Keep raw and source material unchanged.

Use the detailed output guide here:

- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)

## Frontend-First, Backend as Source of Truth

PRISM Studio UI is workflow UX.
Validation and processing logic remains in backend modules.

If behavior is inconsistent, trust backend CLI validation as the canonical result:

```bash
python prism-validator /path/to/project_or_dataset --bids
```

## Common Problems

Problem: Studio starts but page is blank.
- Check terminal output for Flask errors.
- Ensure virtual environment is activated.

Problem: Validation reports missing sidecar JSON.
- Add matching `.json` sidecar or place a valid inherited sidecar at higher dataset level.

Problem: Data imported but task/modality looks wrong.
- Re-check converter mapping and filename patterns.
- Re-run validation to confirm corrected structure.

## Related Pages

- Installation: [INSTALLATION.md](INSTALLATION.md)
- Project workflow: [PROJECTS.md](PROJECTS.md)
- Converter overview: [CONVERTER.md](CONVERTER.md)
- Tools overview: [TOOLS.md](TOOLS.md)
- Detailed command reference: [CLI_REFERENCE.md](CLI_REFERENCE.md)
- Command-based workflows: [CLI_WORKFLOWS.md](CLI_WORKFLOWS.md)
- Hands-on walkthrough: [WORKSHOP.md](WORKSHOP.md)
