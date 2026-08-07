# Project Overview

PRISM Studio is the usual place to work with PRISM. It guides you from an
incoming study file to a structured, validated dataset that is ready to analyse
or share. You do not need to use the command line or understand the repository
layout to complete a study workflow.

## Start in Studio

Open PRISM Studio, then follow the parts of the workflow that apply to your
study:

1. **Create or open a project.** Add the study details that describe your
   dataset.
2. **Import your data.** Use **Converter** for survey, participant, biometrics,
   physiology, or environment files.
3. **Check the result.** Run **Validator**, review any findings, and apply an
   available fix where appropriate.
4. **Add study-specific detail.** Use **Prepare Data** to maintain templates,
   metadata, or scoring recipes when your study needs them.
5. **Export or share.** Prepare the validated dataset in the format required by
   your analysis or sharing destination.

Start Studio with `python prism-studio.py` or, after setup, `rtk studio`. The
[Studio Guide](studio/index.md) explains each screen as you need it.

## What you can do

| In Studio | Use it to |
|---|---|
| **Projects** | Create or open a study workspace, maintain study metadata, and prepare an export-ready dataset |
| **Converter** | Turn surveys, participant data, biometrics, physiology, and environment tables into PRISM/BIDS-compatible files |
| **Validator** | Find data and metadata issues, run optional BIDS checks, and apply available auto-fixes |
| **Prepare Data** | Build templates, complete metadata, and create scoring recipes when your workflow needs them |
| **Export** | Create CSV, SPSS, ZIP, anonymized, ANC, or other shareable outputs |

## Terms you will see

- **PRISM** is the data and metadata model for psychology-focused research data.
- **PRISM Studio** is the application that helps you work with a PRISM dataset.
- A **project** is your working area: study metadata, source material, code,
  derived outputs, and the dataset.
- A **dataset** is the structured data you validate and eventually share.
- **BIDS** remains the baseline where it applies; PRISM adds structure for
  psychology workflows that BIDS does not fully specify.

Read [What is PRISM](WHAT_IS_PRISM.md) for the model and compatibility story.

## Optional tools and technical reference

Most users can stay in Studio. The following options support specific advanced
or automated workflows:

- **Validator CLI** is useful for reproducible checks and continuous integration:
  `prism-validator /path/to/dataset --bids`.
- **Tools CLI** supports import and transformation in scripted workflows:
  `python prism_tools.py --help`. See [CLI Reference](CLI_REFERENCE.md).
- **DataLad** is optional for large datasets that need provenance and large-file
  handling. See [DataLad](DATALAD.md).

### For contributors

| Path | Role |
|---|---|
| `src/` | Canonical backend logic for validation, conversion, export, scoring, and schema-aware behavior |
| `app/src/` | Flask routes and adapter code that wire the UI to backend operations |
| `app/templates/` and `app/static/` | Studio UI templates, styling, and page scripts |
| `docs/` | Read the Docs source pages built with Sphinx and MyST |
| `tests/` | Behavior coverage and example workflows that also help validate documentation accuracy |

User-visible behavior belongs in the workflow docs; implementation details should
point back to the backend as the source of truth.

## What's next

- [Installation](INSTALLATION.md) · [Getting Started](TUTORIAL_BEGINNER.md) ·
  [Studio Guide](studio/index.md)
- [Workshop](WORKSHOP.md) and [Examples](EXAMPLES.md) for guided/sample-driven
  learning; `examples/workshop/` and `tests/` for reusable assets
- [CLI Reference](CLI_REFERENCE.md) and [Error Codes](ERROR_CODES.md)
