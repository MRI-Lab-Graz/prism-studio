# CLI Workflows

Use this guide when you want to work from the terminal rather than from the
Studio web interface.

The CLI path is best for:

- automation
- CI or batch validation
- reproducible scripted workflows
- users who prefer terminal-first work

PRISM remains an add-on to BIDS in the CLI path just as it does in Studio.

## Recommended starting point

If you are new to the terminal workflow, use this order:

1. activate the environment
2. validate a dataset
3. inspect or generate templates and recipes only as needed
4. automate once the manual commands are understood

## 1. Setup and environment

Run setup once from repository root.

macOS and Linux:

```bash
bash setup.sh
```

Windows PowerShell:

```powershell
.\setup.ps1
```

Then activate the project virtual environment before running commands.

macOS and Linux:

```bash
source .venv/bin/activate
```

Windows:

```bat
.venv\Scripts\activate
```

If you see an error about not running inside the PRISM virtual environment,
activate `.venv` and retry.

## 2. Use RTK for the common path

If the repository is available locally, the RTK wrapper is the cleanest entry
point for common workflows.

Examples:

```bash
rtk studio
rtk validator /path/to/dataset --bids
rtk tools --help
rtk test -q
```

Use direct Python entry points when you need a scriptable or explicit command
surface, but prefer RTK for day-to-day usage in this repo.

## 3. Launch Studio from the terminal

If you want the web interface while staying terminal-first:

```bash
python prism-studio.py
```

Expected result:

- local server starts
- Studio becomes available at `http://localhost:5001`

Equivalent RTK path:

```bash
rtk studio
```

## 4. Validate a dataset from the CLI

The validator is the most important command-line entry point.

Basic validation:

```bash
python prism-validator /path/to/dataset
```

PRISM plus BIDS validation:

```bash
python prism-validator /path/to/dataset --bids
```

Preview automatic fixes:

```bash
python prism-validator /path/to/dataset --fix --dry-run
```

Write a machine-readable report:

```bash
python prism-validator /path/to/dataset --format sarif -o prism.sarif
```

Common validation loop:

1. run `--bids`
2. inspect the findings
3. preview fixes with `--fix --dry-run` when appropriate
4. re-run until blocking errors are gone

## 5. Use `prism_tools.py` for conversion and scoring workflows

Use `prism_tools.py` when the task is not just validation.

Show top-level help:

```bash
python prism_tools.py --help
```

Typical uses include:

- survey and biometrics imports
- participant workflows
- recipe execution
- library maintenance
- dataset helpers

Examples:

```bash
python prism_tools.py survey validate --library library/survey
python prism_tools.py recipes surveys --prism /path/to/dataset
python prism_tools.py participants detect-id --input /absolute/path/to/T1.xlsx --json
```

Use [CLI_REFERENCE.md](CLI_REFERENCE.md) for the fuller command matrix.

## 6. Example terminal workflows

### Minimal validation workflow

```bash
source .venv/bin/activate
python prism-validator /path/to/dataset --bids
```

### Validation plus scoring workflow

```bash
source .venv/bin/activate
python prism-validator /path/to/dataset --bids
python prism_tools.py recipes surveys --prism /path/to/dataset
```

### Participants merge preview workflow

```bash
source .venv/bin/activate
python prism_tools.py participants merge \
	--input /absolute/path/to/T1.xlsx \
	--project /absolute/path/to/my-project/project.json \
	--json
```

This is the CLI equivalent of the preview-first safe-merge pattern from Studio.

## 7. Daily repo quality commands

Fast smoke check:

```bash
bash scripts/ci/run_local_smoke.sh
```

Full runtime gate:

```bash
bash scripts/ci/run_runtime_gate.sh
```

Tests:

```bash
pytest
```

## 8. Common mistakes

- forgetting to activate `.venv`
- validating the wrong dataset path
- applying fixes without checking the dry run first
- assuming a saved recipe already produced derivative outputs
- jumping into a deep `prism_tools.py` subcommand without first checking `--help`

## Related pages

- [CLI_REFERENCE.md](CLI_REFERENCE.md)
- [VALIDATOR.md](VALIDATOR.md)
- [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md)
- [WORKSHOP.md](WORKSHOP.md)
