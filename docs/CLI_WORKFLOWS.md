# CLI Workflows

For working from the terminal rather than the Studio web interface — best for
automation, CI/batch validation, reproducible scripted workflows, and terminal-first
users. PRISM remains an add-on to BIDS in the CLI path just as it does in Studio.

If you're new to this: activate the environment → validate a dataset → inspect or
generate templates/recipes only as needed → automate once the manual commands are
understood.

## Setup and daily entry points

Run setup once from the repository root (`bash setup.sh` on macOS/Linux,
`.\setup.ps1` on Windows PowerShell), then activate the virtual environment before
running any commands (`source .venv/bin/activate` / `.venv\Scripts\activate`). If you
see an error about not running inside the PRISM virtual environment, activate
`.venv` and retry.

If the repository is available locally, **RTK** is the cleanest entry point for
common workflows:

```bash
rtk studio
rtk validator /path/to/dataset --bids
rtk tools --help
rtk test -q
```

Use direct Python entry points when you need a scriptable/explicit command surface;
prefer RTK for day-to-day use in this repo. Launching the web interface directly:
`python prism-studio.py` (starts a local server at `http://localhost:5001`).

## Validate a dataset

The validator is the most important CLI entry point:

```bash
prism-validator /path/to/dataset              # basic validation
prism-validator /path/to/dataset --bids       # PRISM + BIDS
prism-validator /path/to/dataset --fix --dry-run   # preview automatic fixes
prism-validator /path/to/dataset --format sarif -o prism.sarif   # machine-readable report
```

Common loop: run `--bids` → inspect findings → preview fixes with `--fix --dry-run`
when appropriate → re-run until blocking errors are gone.

## Conversion and scoring with `prism_tools.py`

Use `prism_tools.py` for anything beyond validation — survey/biometrics imports,
participant workflows, recipe execution, library maintenance, dataset helpers. Show
the full command matrix with `python prism_tools.py --help`, or see
[CLI Reference](CLI_REFERENCE.md).

```bash
python prism_tools.py survey validate --library library/survey
python prism_tools.py recipes surveys --prism /path/to/dataset
python prism_tools.py participants detect-id --input /absolute/path/to/T1.xlsx --json
```

**Example: validation + scoring**

```bash
source .venv/bin/activate
prism-validator /path/to/dataset --bids
python prism_tools.py recipes surveys --prism /path/to/dataset
```

**Example: participants merge preview** — the CLI equivalent of Studio's
preview-first safe-merge pattern:

```bash
python prism_tools.py participants merge \
	--input /absolute/path/to/T1.xlsx \
	--project /absolute/path/to/my-project/project.json \
	--json
```

## Daily repo quality commands

```bash
bash scripts/ci/run_local_smoke.sh     # fast smoke check
bash scripts/ci/run_runtime_gate.sh    # full runtime gate
pytest                                 # tests
```

## Common mistakes

Forgetting to activate `.venv`; validating the wrong dataset path; applying fixes
without checking the dry run first; assuming a saved recipe already produced
derivative outputs; jumping into a deep `prism_tools.py` subcommand without first
checking `--help`.

## What's next

- [CLI Reference](CLI_REFERENCE.md)
- [Validator](studio/validator.md) · [Studio Guide](studio/index.md)
- [Workshop](WORKSHOP.md)
