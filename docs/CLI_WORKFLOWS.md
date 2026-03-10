# CLI Workflows

This guide is for terminal users who want complete command-driven workflows.

PRISM is an add-on to BIDS, not a replacement.

## 1) Setup and Environment

Run setup once from repository root.

macOS/Linux:

```bash
bash setup.sh
```

Windows (PowerShell):

```powershell
.\setup.ps1
```

Activate the project virtual environment before running commands.

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows:

```bat
.venv\Scripts\activate
```

Common issue:
- Error: "You are not running inside the prism virtual environment"
- Fix: Activate `.venv` and rerun the command.

## 2) Run PRISM Studio from Terminal

Purpose: launch the web interface while staying terminal-first.

```bash
python prism-studio.py
```

Expected result:
- Local server starts.
- UI opens at `http://localhost:5001`.

## 3) Validate a Dataset (CLI)

Purpose: validate PRISM extensions and optionally BIDS.

```bash
python prism-validator /path/to/dataset
```

Run PRISM + BIDS validation:

```bash
python prism-validator /path/to/dataset --bids
```

Write a machine-readable report:

```bash
python prism-validator /path/to/dataset --format sarif -o prism.sarif
```

Preview automatic fixes:

```bash
python prism-validator /path/to/dataset --fix --dry-run
```

Apply automatic fixes:

```bash
python prism-validator /path/to/dataset --fix
```

Common issue:
- Error: path not found or empty dataset.
- Fix: verify dataset root path and required BIDS files (`dataset_description.json`, subject folders).

## 4) Use `prism_tools.py`

Purpose: conversion, imports, scoring, and utility tasks.

Show available commands:

```bash
python prism_tools.py --help
```

Survey import from Excel codebook:

```bash
python prism_tools.py survey import-excel --excel surveys.xlsx --library-root library
```

Survey library validation:

```bash
python prism_tools.py survey validate --library library/survey
```

Survey conversion to PRISM dataset:

```bash
python prism_tools.py survey convert --input survey_export.xlsx --output /tmp/my_prism_dataset
```

Biometrics import from Excel codebook:

```bash
python prism_tools.py biometrics import-excel --excel biometrics_codebook.xlsx --sheet 0 --library-root library
```

Run scoring recipes:

```bash
python prism_tools.py recipes surveys --prism /path/to/dataset
python prism_tools.py recipes biometrics --prism /path/to/dataset
```

## 5) End-to-End Minimal Terminal Flow

```bash
source .venv/bin/activate
python prism-validator /path/to/dataset --bids
python prism_tools.py survey validate --library library/survey
python prism_tools.py recipes surveys --prism /path/to/dataset
```

Expected artifacts:
- Validation report in terminal or output file.
- Updated/fixed sidecars when `--fix` is used.
- Derivative scoring outputs for recipe runs.

## 6) Daily Quality Commands

Fast smoke check:

```bash
bash scripts/ci/run_local_smoke.sh
```

Full runtime gate:

```bash
bash scripts/ci/run_runtime_gate.sh
```

Python tests:

```bash
pytest
```

Formatting and linting:

```bash
black .
flake8 .
```

## 7) Where to Go Next

- Full command reference: [CLI_REFERENCE.md](CLI_REFERENCE.md)
- Frontend-first workflows: [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md)
- Walk-through example: [WORKSHOP.md](WORKSHOP.md)
