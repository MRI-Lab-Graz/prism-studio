# PRISM Runtime Runbook (Run-First)

This runbook is the shortest safe path to keep PRISM running day-to-day.

## 1) Activate environment

Always start in repository root:

```bash
cd /path/to/prism-studio
source .venv/bin/activate
```

If `.venv` is missing, run setup (do not install packages manually):

```bash
bash setup.sh
```

## 2) Startup check (Web UI)

```bash
python prism-studio.py
```

Expected:
- no immediate crash,
- app starts and serves UI (default port behavior from app).

Fast smoke alternative (no server start, just entrypoint sanity):

```bash
bash scripts/ci/run_local_smoke.sh
```

## 3) CLI validation check

```bash
python prism.py /path/to/dataset
```

Expected:
- validator runs,
- reports issues/warnings without interpreter/import crash.

## 4) Repository health gate (required)

Use this before/after any change:

```bash
bash scripts/ci/run_runtime_gate.sh
```

Equivalent manual command:

```bash
python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix
```

Expected:
- all three checks pass.

## 5) First-response troubleshooting

### A) Missing virtual environment / wrong interpreter
Symptoms:
- `ModuleNotFoundError`, missing package errors, wrong Python path.

Actions:
1. Ensure repo root.
2. Run `source .venv/bin/activate`.
3. If `.venv` missing or broken: `bash setup.sh`.
4. Re-run the health gate command.

### B) Missing survey templates
Symptoms:
- conversion endpoints report no templates found.

Actions:
1. Check project library path exists (`code/library/survey`).
2. Ensure `survey-*.json` files are present.
3. If project library is empty, check official/global library configuration in UI/settings.
4. Re-run conversion preview first, then full conversion.

### C) Missing ID mapping
Symptoms:
- conversion fails with mapping-required/incomplete mapping errors.

Actions:
1. Confirm mapping file is provided (`.tsv`/`.csv`/`.txt` as required by endpoint).
2. Confirm all source IDs have a mapping row.
3. Place mapping file in expected project locations when needed (project/library workflow).
4. Retry preview endpoint before full run.

## 6) Stop rule (run-first)

If health gate is green and runtime checks pass, stop refactoring.
Only continue when there is a concrete operational issue (crash, conversion failure, security regression).

## 7) Windows equivalent

On Windows, use:

```bat
scripts\ci\run_runtime_gate.bat
```

Fast smoke equivalent:

```bat
scripts\ci\run_local_smoke.bat
```
