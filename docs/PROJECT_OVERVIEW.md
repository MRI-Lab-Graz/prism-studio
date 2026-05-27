# Project Overview

Use this page as the map of the repository and product surface before you dive
into a specific workflow.

PRISM Studio has one backend engine and multiple user-facing entry points:

- the Studio web application for guided workflows
- the validator CLI for direct dataset checks
- the tools CLI for import, conversion, scoring, and utility commands

## What the project currently covers

PRISM Studio supports the full lifecycle of a psychological research dataset.

| Area | What you can do |
|---|---|
| Projects | Create or open projects, maintain study metadata, manage sessions, and prepare export-ready datasets |
| Conversion | Convert surveys, sociodemographics, biometrics, physiology, and environment-style tabular inputs into PRISM/BIDS-compatible files |
| Validation | Run PRISM validation, optional BIDS validation, inspect structured findings, and apply available auto-fixes |
| Templates and metadata | Build or edit survey and biometrics templates, complete JSON sidecars, and maintain project-local libraries |
| Scoring and analysis | Run recipes, compute derived scores, and export analysis-ready outputs such as CSV or SPSS |
| Export and sharing | Create shareable ZIPs, anonymized exports, ANC export, and other downstream packaging workflows |
| Automation | Use `prism.py`, `prism_tools.py`, `prism-validator`, and `rtk` for scripted and CI-oriented workflows |

## Product surfaces

### Studio web interface

Use Studio when you want a guided workflow and UI help.

Typical pages:

- **Projects** for project setup, metadata, and export
- **Converter** for survey, participants, biometrics, physio, and environment imports
- **Validator** for project or dataset checks
- **Tools** for template editing, file management, JSON editing, recipes, and library workflows

Start it with:

```bash
python prism-studio.py
```

or, after setup:

```bash
rtk studio
```

### Validator CLI

Use the validator CLI when you want a fast check, reproducible scripting, or CI.

```bash
python prism-validator /path/to/dataset --bids
```

Key capabilities include:

- PRISM validation with structured error codes
- optional BIDS validation alongside PRISM
- JSON output for machine-readable reports
- dry-run and fix modes for supported issues
- schema-version selection and schema inspection

### Tools CLI

Use the tools CLI when you want import and transformation workflows without the web UI.

```bash
python prism_tools.py --help
```

It exposes command groups for surveys, participants, biometrics, environment,
recipes, anonymization, template export, and more.

## How the repository is organized

The repository is intentionally split into a thin web layer and a larger backend
engine.

| Path | Role |
|---|---|
| `src/` | Canonical backend logic for validation, conversion, export, scoring, and schema-aware behavior |
| `app/src/` | Flask routes and adapter code that wire the UI to backend operations |
| `app/templates/` and `app/static/` | Studio UI templates, styling, and page scripts |
| `docs/` | Read the Docs source pages built with Sphinx and MyST |
| `tests/` | Behavior coverage and example workflows that also help validate documentation accuracy |

This separation matters for documentation: user-visible behavior belongs in the
workflow docs, while implementation details should point back to the backend as
the source of truth.

## Core concepts you should keep separate

### PRISM vs PRISM Studio

- **PRISM** is the data and metadata model.
- **PRISM Studio** is the software that helps you create, validate, convert, score, and export datasets that follow that model.

### Project vs dataset

- A **project** is the working area that holds study-level files, metadata, code, library assets, derivatives, and source material.
- A **dataset** is the data structure inside that project that you validate and eventually share.

### BIDS vs PRISM

- BIDS stays the baseline for standard neuroimaging-compatible organization.
- PRISM adds structure and metadata for psychological research workflows that BIDS does not fully specify.

## Typical user journeys

### Journey 1: First study in Studio

1. Install PRISM Studio.
2. Create a project in **Projects**.
3. Import survey or participant data in **Converter**.
4. Run **Validator** with optional BIDS checks.
5. Add templates or recipes in **Tools**.
6. Export a cleaned or anonymized dataset.

### Journey 2: Validate an existing dataset from the terminal

1. Open a terminal in the repo or installed environment.
2. Run `python prism-validator /path/to/dataset --bids`.
3. Review the result codes and fix the reported issues.
4. Re-run until blocking errors are cleared.

### Journey 3: Work with large datasets and provenance

1. Create or open a project that uses DataLad-aware storage.
2. Keep the project root as the controlling dataset.
3. Use Studio or CLI workflows without breaking BIDS compatibility.
4. Export from a copy when you need anonymization or defacing.

See [DATALAD.md](DATALAD.md) for the public DataLad guidance.

## Best example sources in this repository

- [WORKSHOP.md](WORKSHOP.md) for a guided end-to-end exercise
- [EXAMPLES.md](EXAMPLES.md) for sample-driven learning paths
- [CLI_REFERENCE.md](CLI_REFERENCE.md) for command surfaces
- [ERROR_CODES.md](ERROR_CODES.md) for validation interpretation
- `examples/workshop/` for reusable teaching assets
- `tests/` for stable behavior examples and edge cases

## Where to go next

- [WHAT_IS_PRISM.md](WHAT_IS_PRISM.md) for the model and compatibility story
- [INSTALLATION.md](INSTALLATION.md) for setup choices
- [QUICK_START.md](QUICK_START.md) for a first successful workflow
- [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md) for page-by-page navigation
