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
4. `survey` handlers ✅
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
  - `commands/survey.py` (including `survey convert`)
  - `commands/recipes.py`
- Kept compatibility by delegating from `app/prism_tools.py` wrappers.
- Centralized CLI dispatch routing in `app/src/cli/dispatch.py` and wired `app/prism_tools.py` to it.
- Centralized CLI parser construction in `app/src/cli/parser.py` and wired `app/prism_tools.py` main to it.
- Introduced `app/src/cli/entrypoint.py` for runtime wiring and reduced `app/prism_tools.py` to a thin compatibility launcher.
- Started script-folder reorganization with compatibility wrappers:
  - moved duplicate-diagnostics scripts to `scripts/dev/`
  - retained old paths as wrappers to avoid workflow breakage
- Moved environment-build scripts to `scripts/data/` and kept old entry paths as wrappers.
- Moved additional scripts with wrappers:
  - `scripts/maintenance/generate_recipes.py`
  - `scripts/data/harvest_psytoolkit.py`

## Learned Lessions

- Start with contract tests before moving code: refactoring speed increases and risk drops.
- Use wrapper delegation first, then remove legacy code only after a full extraction cycle.
- Keep extraction batches small and domain-focused (`library`, `dataset`, etc.) to simplify review.
- Validate after every batch with targeted CLI tests plus repository safety checks.
- Keep BIDS compatibility constraints explicit in refactor decisions.
- Large handler moves are safer when performed as pure function relocation + thin wrapper delegation.
- Keep temporary lifecycle objects (`TemporaryDirectory`) scoped exactly as in legacy behavior during migration.
- Moving dispatch first (before full parser migration) reduces risk and makes final parser extraction straightforward.
- Returning both root parser and named subgroup parser handles from the parser module keeps help fallbacks stable during dispatch migration.
- Keeping the compatibility launcher minimal helps detect accidental logic drift and prevents stale helper code from lingering in entry scripts.
- Script reorganization is safest when done in small batches with old-path wrappers so docs/automation do not break immediately.
- Wrapping moved scripts with runpy keeps behavior and arguments identical while allowing immediate folder cleanup.
- Categorizing by script purpose (`dev`, `data`, `maintenance`) creates a clearer contributor mental model without immediate disruption.

## Immediate next step

- Continue script-folder reorganization in batches (`scripts/release` and remaining root scripts) with compatibility wrappers, then update docs/automation references incrementally.
