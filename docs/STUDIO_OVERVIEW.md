# PRISM Studio Overview

PRISM Studio is the guided web workflow for PRISM. Use it when you want to move
through project setup, conversion, validation, scoring, and export in one place.

Use the CLI when you want automation, CI, or repeated batch processing. Use the
Studio when you want the same backend behavior with a workflow-oriented UI.

## Start Studio

If you still need setup help, start with [INSTALLATION.md](INSTALLATION.md).

From the repository root:

```bash
python prism-studio.py
```

or:

```bash
rtk studio
```

Open `http://localhost:5001` if the browser does not open automatically.

## Recommended path through the interface

For most studies, use this order:

1. **Projects**: create or open the project and complete the key metadata.
2. **Converter**: bring source files into PRISM/BIDS-compatible structure.
3. **Validator**: run PRISM checks and optional BIDS checks.
4. **Tools**: complete templates, edit JSON metadata, manage files, and build recipes.
5. **Projects export** or **Analysis outputs**: package, anonymize, and share results.

## Page map

| Page | Use it for | Typical output |
|---|---|---|
| Home | Getting oriented and jumping into common tasks | Quick access to the main workflow |
| Projects | Project creation, project metadata, methods text, export | A structured project and updated study-level metadata |
| Converter | Survey, participants, biometrics, physio, and environment imports | PRISM/BIDS-compatible files in the project |
| Validator | Dataset checks and issue review | Structured findings with codes and details |
| Tools | Templates, JSON editing, recipes, file management, library workflows | Completed metadata, scoring rules, and safer edits |
| Results | Reviewing prior runs and outputs | Downloadable reports and run history |

## Projects: where the workflow starts

UI path: `Projects`

Use the Projects page to create the working structure that later steps depend on.

Typical root structure:

```text
project_name/
├── dataset_description.json
├── project.json
├── CITATION.cff
├── CHANGES
├── README.md
├── .bidsignore
├── .prismrc.json
├── sourcedata/
├── derivatives/
└── code/
    ├── library/
    └── recipes/
```

`participants.tsv`/`participants.json` are not part of this creation-time tree —
they're written once you run the participants/sociodemographics import step.

The exact contents will grow with the study, but the basic split stays the same:

- `sourcedata/` for incoming material
- validated dataset files at project root
- `code/` for local recipes, templates, and scripts
- `derivatives/` for processed outputs

If you use DataLad, keep the project root as the controlling dataset and follow
the guidance in [DATALAD.md](DATALAD.md).

## Converter: where source files become structured data

UI path: `Converter`

Use the Converter when you have source material such as Excel, CSV, TSV, SPSS,
or LimeSurvey exports.

The converter currently supports multiple workflow slices, including:

- surveys
- sociodemographics and participants files
- biometrics
- physiology
- environment-style tables

Two common entry points are:

- [SURVEY_IMPORT.md](SURVEY_IMPORT.md) for survey data
- [PARTICIPANTS_MAPPING.md](PARTICIPANTS_MAPPING.md) for participant workflows

### Important participants decision

The participants workflow is organized around three cases:

- **Case 1**: the import file is the source of truth
- **Case 2**: modify existing project files
- **Case 3**: merge safely from an imported file

Pick the case before preview and save. Mixing the cases is one of the easiest
ways to create confusion in a first project.

## Validator: where structure becomes trustworthy

UI path: `Validator`

Use the Validator to check:

- filename patterns
- required files
- JSON sidecars
- modality-specific schema content
- optional BIDS compatibility in the same run

Validation levels:

- **Error**: must fix before treating the dataset as valid
- **Warning**: should fix soon
- **Suggestion**: recommended improvement

Typical loop:

1. Run validation.
2. Open the finding details.
3. Fix the issue manually or use auto-fix where offered.
4. Re-run validation.

## Tools: where metadata and scoring mature

UI path: `Tools`

The Tools area contains the supporting workflows that make a project reusable.

Main tools:

- **Template Editor** for survey and biometrics templates
- **JSON Editor** for direct metadata editing with schema awareness
- **Recipe Builder** for scoring and derived variables
- **File Management** for safer renaming and organization tasks
- **Library** workflows for reusable assets

Good next reads:

- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- [TOOLS.md](TOOLS.md)

## Export and downstream use

Once the project is validated and enriched with metadata or recipes, use the
project export workflows and the analysis/output workflows to create packages for
sharing or analysis.

Typical outcomes:

- derivatives in `derivatives/`
- shareable ZIP exports
- anonymized exports
- downstream analysis files such as CSV or SPSS

See [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md) for the deeper guide.

## Studio and backend ownership

PRISM Studio is a guided interface, not a separate logic layer. The backend in
`src/` remains the source of truth for validation, conversion, export, and
scoring behavior.

If you need to confirm a result independently, use the CLI against the same
project or dataset:

```bash
python prism-validator /path/to/project_or_dataset --bids
```

## Common first-use problems

### The page opens but stays blank

- Check the terminal where Studio was launched.
- Confirm the repository virtual environment is active for source usage.

### Validation reports a missing sidecar

- Add the matching `.json` sidecar.
- Or add a valid inherited sidecar at the correct higher level.

### Imported data landed under the wrong task or modality

- Re-check the converter mapping and filename assumptions.
- Re-run validation to confirm the corrected structure.

## Related pages

- [PROJECTS.md](PROJECTS.md)
- [CONVERTER.md](CONVERTER.md)
- [VALIDATOR.md](VALIDATOR.md)
- [TOOLS.md](TOOLS.md)
- [CLI_REFERENCE.md](CLI_REFERENCE.md)
- [WORKSHOP.md](WORKSHOP.md)
