# PRISM Studio (Web Interface)

Use this page when you want the high-level picture of the web interface itself.

This page complements [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md):

- `STUDIO_OVERVIEW.md` is the main learner path through the product
- this page summarizes what the web interface exposes and where specific helper
	workflows live

## What PRISM Studio the web interface is

PRISM Studio is the browser-based interface launched by `prism-studio.py`.

It provides guided access to:

- project setup
- conversion and import
- validation
- metadata editing
- template and recipe workflows
- export and reporting

For installation, use [INSTALLATION.md](INSTALLATION.md).
For terminal automation, use [CLI_REFERENCE.md](CLI_REFERENCE.md).

## Start Studio

macOS and Linux:

```bash
source .venv/bin/activate
python prism-studio.py
```

Windows:

```bat
.venv\Scripts\activate
python prism-studio.py
```

Open `http://localhost:5001` if it does not open automatically.

## What the interface is best at

The web interface is strongest when you want:

- guided workflows instead of raw commands
- project-bound editing with visible state
- preview-first conversion steps
- easier metadata completion than raw JSON editing

## Common web-interface tasks

### Upload and validate a dataset

The validation-oriented web path supports folder and ZIP-based inputs.

For large datasets, Studio can support a structure-focused upload path where
metadata and structural information are reviewed without moving every large
binary first.

Use this when the goal is to validate structure, filenames, and sidecar logic
without fully transferring or materializing all payloads.

### Edit JSON safely

The JSON Editor helps with direct sidecar work while still staying within a
schema-aware workflow.

Typical use:

- complete sidecars after validation findings
- inspect metadata without hand-editing files in an external editor

### Work with templates

The Template Editor is the main UI for survey and biometrics template work.

It supports:

- loading templates from library paths
- creating new schema-aware templates
- validating the current editor state
- saving to the project library

### Work with participants metadata

The web interface also includes participant-oriented workflows such as
annotation-friendly editing and integration-oriented metadata preparation.

### Generate methods text

Studio can generate draft methods text from project and library metadata, which
is useful for reports and manuscripts.

### Export survey structures or downstream packages

The web interface exposes survey export, shareable project export, anonymized
export, ANC export, and related output workflows.

## First-time-use advice

- start with a small example project such as the workshop material
- validate early rather than waiting until the whole dataset is assembled
- use the interface to understand the workflow, then move to CLI automation only
	when the steps are already clear

## Related pages

- [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md)
- [PROJECTS.md](PROJECTS.md)
- [VALIDATOR.md](VALIDATOR.md)
- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
