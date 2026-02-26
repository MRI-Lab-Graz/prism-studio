# CLI Modularization Roadmap

This roadmap targets backend/script modularization while preserving PRISM's core rule:
**PRISM extends BIDS; it does not replace BIDS.**

## Goals

- Keep all current CLI commands and options stable during refactoring.
- Reduce monolithic orchestration in `app/prism_tools.py`.
- Organize `scripts/` by purpose and lifecycle.
- Keep Web UI behavior based on the same backend core path.

## Phase 1 — Contract Lock (completed)

- Add CLI contract tests for help surfaces and key subcommands.
- Ensure CI catches accidental command/argument regressions.
- Baseline tests before moving parser/handler code.

Deliverable:
- `tests/test_prism_tools_cli_contract.py`

## Phase 2 — CLI Package Skeleton (completed)

Target structure:

```text
app/src/cli/
  __init__.py
  parser.py
  dispatch.py
  commands/
    __init__.py
    survey.py
    biometrics.py
    recipes.py
    dataset.py
    anonymize.py
    convert.py
    library.py
  services/
    __init__.py
    ids.py
    sidecars.py
    paths.py
```

Principles:
- Parser wiring separated from command implementation.
- One command domain per module.
- Shared logic moved to `services/`.

## Phase 3 — Incremental Extraction (in progress)

Recommended order (lowest risk first):

1. `library` + `dataset` handlers ✅
2. `convert` + `anonymize` handlers ✅
3. `biometrics` handlers ✅
4. `survey` handlers ✅ (support handlers)
5. `recipes` handlers ✅

After each extraction:
- Run contract tests + targeted functional tests.
- Keep old import paths working until migration is complete.

## Phase 4 — Script Reorganization

Proposed `scripts/` layout:

```text
scripts/
  setup/
  ci/
  dev/
  data/
  release/
  maintenance/
```

Migration rules:
- Move scripts in small batches.
- Leave compatibility wrappers in old paths for one release cycle.
- Update docs and internal references after each batch.

## Phase 5 — Cleanup and Hardening

- Remove temporary wrappers after one release cycle.
- Add import boundary checks (no command module reaches unrelated domains).
- Update developer docs for new layout and contribution flow.

## Progress Log

- Added CLI contract tests to lock command/help surface.
- Created `app/src/cli/` scaffold (`parser.py`, `dispatch.py`, `commands/`, `services/`).
- Extracted command modules:
  - `commands/library.py`
  - `commands/dataset.py`
  - `commands/convert.py`
  - `commands/anonymize.py`
  - `commands/biometrics.py`
  - `commands/survey.py` (safe support handlers)
  - `commands/recipes.py`
- Kept compatibility by delegating from `app/prism_tools.py` wrappers.

## Learned Lessions

- Start with contract tests before moving code: refactoring speed increases and risk drops.
- Use wrapper delegation first, then remove legacy code only after a full extraction cycle.
- Keep extraction batches small and domain-focused (`library`, `dataset`, etc.) to simplify review.
- Validate after every batch with targeted CLI tests plus repository safety checks.
- Keep BIDS compatibility constraints explicit in refactor decisions.

## Immediate next step

- Extract the remaining `survey convert` handler into `commands/survey.py`,
  then centralize parser/dispatch wiring in `app/src/cli/parser.py` + `dispatch.py`.
