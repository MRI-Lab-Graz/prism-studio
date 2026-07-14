# Project Overview

The map of the repository and product surface before you dive into a specific
workflow. PRISM Studio has one backend engine and multiple user-facing entry
points: the Studio web app, the validator CLI, and the tools CLI.

## What you can do

| Area | What you can do |
|---|---|
| Projects | Create or open projects, maintain study metadata, and prepare export-ready datasets |
| Conversion | Convert surveys, sociodemographics, biometrics, physiology, and environment-style tabular inputs into PRISM/BIDS-compatible files |
| Validation | Run PRISM validation, optional BIDS validation, inspect structured findings, and apply available auto-fixes |
| Templates and metadata | Build or edit survey and biometrics templates, complete JSON sidecars, and maintain project-local libraries |
| Scoring and analysis | Run recipes, compute derived scores, and export analysis-ready outputs such as CSV or SPSS |
| Export and sharing | Create shareable ZIPs, anonymized exports, ANC export, and other downstream packaging workflows |
| Automation | Use `prism.py`, `prism_tools.py`, `prism-validator`, and `rtk` for scripted and CI-oriented workflows |

## Product surfaces

**Studio web interface** — a guided workflow with UI help: **Projects** (setup,
metadata, export), **Converter** (survey/participants/biometrics/physio/environment
imports), **Validator**, **Prepare Data** (Template Editor, Recipe Builder), **Modify
in PRISM** (File Management, JSON Editor). Start with `python prism-studio.py` or,
after setup, `rtk studio`. Full page-by-page detail: [Studio Guide](studio/index.md).

**Validator CLI** — fast checks, reproducible scripting, CI:
`prism-validator /path/to/dataset --bids`. Structured error codes, optional BIDS
validation, JSON output, dry-run/fix modes, schema-version selection.

**Tools CLI** — import/transformation without the web UI: `python prism_tools.py --help`.
Command groups for surveys, participants, biometrics, environment, recipes,
anonymization, template export, and more. See [CLI Reference](CLI_REFERENCE.md).

## How the repository is organized

| Path | Role |
|---|---|
| `src/` | Canonical backend logic for validation, conversion, export, scoring, and schema-aware behavior |
| `app/src/` | Flask routes and adapter code that wire the UI to backend operations |
| `app/templates/` and `app/static/` | Studio UI templates, styling, and page scripts |
| `docs/` | Read the Docs source pages built with Sphinx and MyST |
| `tests/` | Behavior coverage and example workflows that also help validate documentation accuracy |

User-visible behavior belongs in the workflow docs; implementation details should
point back to the backend as the source of truth.

## Core concepts

- **PRISM vs. PRISM Studio** — PRISM is the data/metadata model; PRISM Studio is the
  software that helps you create, validate, convert, score, and export datasets
  following that model.
- **Project vs. dataset** — a project is the working area holding study-level files,
  metadata, code, library assets, derivatives, and source material; a dataset is the
  data structure inside it that you validate and eventually share.
- **BIDS vs. PRISM** — BIDS stays the baseline for standard neuroimaging-compatible
  organization; PRISM adds structure and metadata for psychological research
  workflows BIDS doesn't fully specify.

## Typical journeys

**First study in Studio**: install → create a project → import survey/participant
data via Converter → run Validator (BIDS checks on by default) → add templates or
recipes via Prepare Data → export a cleaned/anonymized dataset.

**Validate an existing dataset from the terminal**: `prism-validator /path/to/dataset --bids`
→ review result codes → fix reported issues → re-run until blocking errors clear.

**Large datasets with provenance**: create/open a DataLad-aware project → keep the
project root as the controlling dataset → work via Studio or CLI without breaking
BIDS compatibility → export from a copy when you need anonymization or defacing. See
[DataLad](DATALAD.md).

## What's next

- [What is PRISM](WHAT_IS_PRISM.md) for the model and compatibility story
- [Installation](INSTALLATION.md) · [Quick Start](QUICK_START.md) ·
  [Studio Guide](studio/index.md)
- [Workshop](WORKSHOP.md) and [Examples](EXAMPLES.md) for guided/sample-driven
  learning; `examples/workshop/` and `tests/` for reusable assets
- [CLI Reference](CLI_REFERENCE.md) and [Error Codes](ERROR_CODES.md)
