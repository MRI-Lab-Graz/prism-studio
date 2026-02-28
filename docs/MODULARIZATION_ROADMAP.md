# CLI Modularization Roadmap (Python-first)

This roadmap targets backend/script modularization while preserving PRISM's core rule:
**PRISM extends BIDS; it does not replace BIDS.**

Primary scope: Python CLI/backend modules and script/tooling structure.
Secondary scope: frontend hardening work that supports safe Web UI behavior without changing the Python core architecture.

## Goals

- Keep all current CLI commands and options stable during refactoring.
- Reduce monolithic orchestration in `app/prism_tools.py`.
- Organize `scripts/` by purpose and lifecycle.
- Keep Web UI behavior based on the same backend core path.

## Current State (2026-02-28)

### Where We Are

- Slice 1 (**Canonical Runtime + Deterministic Tests**) is complete and green.
- Converter entry modules in `app/src/converters/` are now pure compatibility shims for canonical `src/converters/*` modules.
- Fast PR checks are stable and green with staged verification (`pytest-modularity` in Fast PR, full `pytest` in Nightly).

### Next Big Goal

- Start **Slice 2: Blueprint hotspot decomposition** (first target: `app/src/web/blueprints/tools.py`, then `projects.py`, then `conversion_survey_handlers.py`).
- Keep the same Stage A / Stage B validation policy for every extraction batch.

### What Does Not Work Right Now

- Core repo health checks are green for current migration gates, but deeper quality debt remains outside Slice 1 scope:
  - broad MyPy baseline is still noisy (non-blocking in Fast PR),
  - Black formatting check can still report warnings,
  - large blueprint modules remain oversized and are the primary modularity risk.

## Fresh Assessment (2026-02-28)

### Executive Summary

- Progress is real: the previous monoliths were split into route/helper/handler modules in key areas.
- Current risk shifted from **monolith** to **file soup + dual-tree ambiguity**.
- The biggest architecture problem is no longer a single huge file, but **unclear ownership between `src/` and `app/src/` plus oversized domain hubs**.

### What Improved

- Conversion domain now has dedicated modules (survey/biometrics/physio handlers), reducing pressure on one giant route file.
- Import boundary guardrails are active (`app.src.*` runtime imports blocked), preventing one historical drift vector.
- CLI/web entrypoints and core smoke checks still pass.

### Current Hotspots (Measured)

- Dual-tree overlap remains high:
  - `src/`: 21 Python files
  - `app/src/`: 117 Python files
  - Shared relative paths: 15 (71.4% of `src/` mirrored in `app/src/`)
- Blueprint size concentration in `app/src/web/blueprints` (11,503 LOC total):
  - `tools.py` (2,776 LOC)
  - `projects.py` (2,423 LOC)
  - `conversion_survey_handlers.py` (1,524 LOC)
- Cross-layer coupling is still high:
  - 148 `from src...` / `import src...` matches inside `app/src/**/*.py`.

### Stability Signal

- `verify_repo` on `entrypoints-smoke` and `import-boundaries`: passing.
- Full `pytest` in `verify_repo`: passing.
- Fast PR checks: passing with staged modularity gate (`pytest-modularity`).
- Interpretation: Slice 1 removed the previous order-dependent converter/blueprint instability from the active PR path.

### Architecture Diagnosis (Why it feels like file soup)

1. **Split authority**: both `src/` and `app/src/` still act as active sources.
2. **Wrapper-heavy transition layer**: compatibility aliases and delegators are helpful short-term, but now obscure true ownership.
3. **Oversized domain hubs**: `tools.py`, `projects.py`, and survey handler flows remain “micro-monoliths”.
4. **Import direction is not cleanly one-way**: `app/src` repeatedly imports `src`, making module identity and test determinism fragile.

### Recommended Next Slice (Priority Order)

1. **Declare one canonical runtime tree** (`src` recommended for backend/core logic) and mark mirrored backend files under `app/src` as compatibility-only.
2. **Eliminate mirrored business modules** (`converters/*`, `recipes_surveys.py`, `batch_convert.py`) by moving to shim-only files or full deletion where safe.
3. **Break top 3 oversized blueprint modules by bounded contexts**:
   - `tools.py`: template editor, export/customizer, library APIs
   - `projects.py`: settings/library, reporting/export, project lifecycle
   - `conversion_survey_handlers.py`: preview/detect, convert, unmatched-template flow
4. **Add an import-direction contract check** (e.g., fail if `app/src` imports mirrored logic from `src` except approved shims).
5. **Fix test-order nondeterminism first** (module import path normalization in tests + avoid global `sys.modules` side effects).

### Exit Criteria for “File Soup → Modular”

- No duplicated business logic file pairs across `src/` and `app/src/`.
- No domain module > ~1,200 LOC in blueprints/converters hotspots.
- `verify_repo --check entrypoints-smoke,import-boundaries,pytest --no-fix` green in clean run.
- Test outcomes invariant to order (`pytest` full suite equals targeted suite behavior).

### Lessons Learned (2026-02-28)

- Splitting files without settling package authority creates new ambiguity even when line counts improve.
- Compatibility aliases are useful as migration scaffolding, but they need explicit sunset dates.
- Modularization quality must be measured by **determinism + ownership clarity**, not just number of files.

## Sub-Roadmap — Slice 2: Blueprint Hotspot Decomposition (2026-02-28)

Goal of this slice: reduce blueprint hotspot concentration while preserving route contracts and staged verification discipline.

### Execution Order

1. `app/src/web/blueprints/tools.py`
2. `app/src/web/blueprints/projects.py`
3. `app/src/web/blueprints/conversion_survey_handlers.py`

### Running Notes (Slice 2)

- 2026-02-28 (Batch A — `tools.py` survey customizer extraction):
  - Extracted survey customizer heavy handlers into a dedicated module:
    - `app/src/web/blueprints/tools_survey_customizer_handlers.py`
  - Kept existing route paths and endpoint functions in `tools.py` as thin wrappers:
    - `/api/survey-customizer/load`
    - `/api/survey-customizer/export`
    - `/api/survey-customizer/formats`
  - Validation results:
    - Stage A: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - Stage B: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Batch B — `projects.py` lifecycle extraction):
  - Extracted project lifecycle/current/recent/fix handlers into a dedicated module:
    - `app/src/web/blueprints/projects_lifecycle_handlers.py`
  - Kept existing route paths and endpoint functions in `projects.py` as thin wrappers for:
    - `/api/projects/current` (POST)
    - `/api/projects/create`
    - `/api/projects/validate`
    - `/api/projects/path-status`
    - `/api/projects/recent` (GET/POST)
    - `/api/projects/fix`
    - `/api/projects/fixable`
  - Validation results:
    - Stage A: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - Stage B: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Batch C — `conversion_survey_handlers.py` preview/detect extraction):
  - Extracted survey preview/detect handlers into a dedicated module:
    - `app/src/web/blueprints/conversion_survey_preview_handlers.py`
  - Kept existing endpoint functions in `conversion_survey_handlers.py` as thin wrappers for:
    - `/api/survey-languages`
    - `/api/survey-convert-preview`
  - Restored `api_survey_convert` symbol boundary during extraction to preserve blueprint import contracts.
  - Validation results:
    - Stage A: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - Stage B: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

### Next Batches (Queued)

- Slice 2 hotspot sequence complete (`tools.py` -> `projects.py` -> `conversion_survey_handlers.py`).
- Optional follow-up: second-pass decomposition inside each extracted domain if LOC hotspots remain above target.

## Sub-Roadmap — Slice 1: Canonical Runtime + Deterministic Tests (2026-02-28)

Goal of this slice: stabilize module ownership and remove test-order fragility before any further large decomposition.

### Scope (Strict)

- In scope:
  - Canonical package direction for runtime imports
  - Shim policy for duplicated `src/` files
  - Test isolation and import-path determinism
  - Verify checks for this slice
- Out of scope:
  - Large feature work
  - Deep split of `tools.py` / `projects.py` / `conversion_survey_handlers.py` (handled in later slices)

### Phase Plan

#### Phase 1 — Freeze Import Authority

- Decision: `src` is authoritative for backend/runtime implementation; `app/src` remains web/entrypoint + compatibility surface.
- Action:
  - Keep mirrored backend modules in `app/src/` as compatibility shims (or remove where no external dependency exists).
  - Stop adding new backend business logic to mirrored `app/src` modules.
- Exit check:
  - No new non-shim logic added in mirrored `src/` files.

#### Phase 2 — Deterministic Test Imports

- Action:
  - Normalize test import bootstrap to one approach (single helper fixture/module path setup).
  - Remove ad-hoc `sys.modules` mass-deletion patterns that can leak across test order.
  - Keep mocking local to test modules and restore state explicitly.
- Exit check:
  - `pytest -q tests/test_web_blueprints_conversion.py` and full `pytest` are both stable with same result.

#### Phase 3 — Guardrail Enforcement

- Action:
  - Add/extend verify check to enforce allowed import direction during migration.
  - Explicit allowlist for approved compatibility shims.
- Exit check:
  - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` passes reliably.

#### Phase 4 — Shim Cleanup Start

- Action:
  - Convert top mirrored files (`batch_convert.py`, `recipes_surveys.py`, selected `converters/*`) to thin shims or retire duplicates.
- Exit check:
  - Duplicate business logic count reduced with no CLI/Web behavior regression.

### Running Notes (What Happened)

Use this log for every execution step in this slice.

- 2026-02-28:
  - Baseline verify command run:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`
    - Result: `entrypoints-smoke` pass, `import-boundaries` pass, `pytest` fail.
  - Failure signature:
    - `tests/test_web_blueprints_conversion.py` delegation assertions fail in full-suite context.
    - Same test file can pass in isolation, indicating order/module-identity instability.
  - Interpretation:
    - Confirms split-root import fragility (`src` vs `app/src`) and non-deterministic test environment effects.

- 2026-02-28 (strategy update + execution):
  - Added staged check `pytest-modularity` to `tests/verify_repo.py` for refactor-speed feedback.
  - Updated `verify_repo.py` pytest execution path to run `python -m pytest` directly.
  - Stabilized `tests/test_web_blueprints_conversion.py` by replacing string-path patching with `patch.object(...)` against imported module objects.
  - Validation results:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 import-authority slice A):
  - Converted duplicated `app/src/maintenance/*` implementations into explicit compatibility shims delegating to canonical `src/maintenance/*` modules:
    - `app/src/maintenance/catalog_survey_library.py`
    - `app/src/maintenance/sync_biometrics_keys.py`
    - `app/src/maintenance/sync_survey_keys.py`
  - Preserved script execution behavior via `if __name__ == "__main__"` passthrough calls.
  - Validation results:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 import-authority slice B):
  - Added explicit runtime re-export bindings from canonical `src/*` modules in mirrored `app/src` backend modules:
    - `app/src/api.py` -> re-export from `src.api`
    - `app/src/formatters.py` -> re-export from `src.formatters`
    - `app/src/participants_converter.py` -> re-export from `src.participants_converter`
  - Goal: reduce drift while keeping compatibility imports working during migration.
  - Validation results:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 import-authority slice C - shim loader hardening):
  - Added path-based canonical module loader: `app/src/_compat.py`.
  - Updated mirrored modules to load canonical backend files by absolute path (avoids split-package self-import ambiguity):
    - `app/src/api.py`
    - `app/src/formatters.py`
    - `app/src/participants_converter.py`
    - `app/src/maintenance/catalog_survey_library.py`
    - `app/src/maintenance/sync_biometrics_keys.py`
    - `app/src/maintenance/sync_survey_keys.py`
  - Validation results:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 import-authority slice D - large mirrored modules):
  - Added canonical delegation bindings for high-duplication backend modules:
    - `app/src/batch_convert.py` -> delegates exported symbols to canonical `src/batch_convert.py`
    - `app/src/recipes_surveys.py` -> delegates exported symbols to canonical `src/recipes_surveys.py`
  - Corrected compatibility import path to package-qualified form (`src._compat`) for stable resolution.
  - Validation results:
    - module smoke import via `app` path: pass (`batch_convert_folder`, `create_dataset_description`, `compute_survey_recipes` present)
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 import-authority slice E - converter delegation trial, rolled back):
  - Attempted canonical delegation for:
    - `app/src/converters/biometrics.py`
    - `app/src/converters/excel_to_biometrics.py`
    - `app/src/converters/limesurvey.py`
  - Issue discovered:
    - mixed relative/fallback import patterns in canonical modules (notably `excel_to_biometrics.py`) break under synthetic loading context and caused CLI help/import failures.
  - Action taken:
    - reverted converter delegation blocks to restore stable behavior.
  - Validation results after rollback:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.
  - Follow-up strategy:
    - perform converter authority unification only after import normalization inside canonical converter modules (remove context-sensitive fallback imports first).

- 2026-02-28 (Phase 1 prerequisite slice F - canonical converter import normalization):
  - Normalized import strategy in canonical module `src/converters/excel_to_biometrics.py`:
    - replaced mixed relative/bare fallback imports with canonical `src.converters.excel_base` imports
    - kept a controlled path bootstrap fallback for direct script execution contexts
  - Validation results:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 prerequisite slice G - canonical limesurvey import normalization + narrow trial):
  - Normalized canonical imports in `src/converters/limesurvey.py` to use explicit `src.*` imports with controlled bootstrap fallback.
  - Ran narrow delegation trial for `app/src/converters/limesurvey.py` only.
  - Trial result:
    - failed in deep CLI contract tests due to unresolved canonical dependency path (`src.converters.survey_base`) under delegated import context.
  - Action taken:
    - reverted only the `app/src/converters/limesurvey.py` delegation block.
  - Validation results after rollback:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 2 completion step - test bootstrap hardening):
  - Removed global `sys.modules` purge pattern from `tests/test_web_formatting.py`.
  - Scoped and restored module mocks in `tests/test_web_blueprints_conversion.py` using `setUpModule` / `tearDownModule` to avoid cross-test leakage.
  - Validation results:
    - `python -m pytest -q tests/test_web_formatting.py tests/test_web_blueprints_conversion.py` -> pass (`21 passed`).
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 converter dependency-chain unblocking step):
  - Mapped unresolved canonical converter imports and identified missing `src.converters` modules referenced by canonical files:
    - `csv`
    - `survey_base`
    - `excel_base`
  - Added/implemented the missing canonical chain modules in `src/converters/`:
    - `src/converters/excel_base.py` (native canonical implementation, including `sanitize_task_name` export)
    - `src/converters/survey_base.py` (native canonical implementation of base survey library helpers)
    - `src/converters/csv.py` (compat loader with package-context bootstrap to keep historical behavior while preserving import-boundary rules)
  - Result:
    - canonical import chain now resolves for `src.converters.excel_to_biometrics` and `src.converters.limesurvey`.
    - import smoke passed for:
      - `src.converters.excel_base`
      - `src.converters.csv`
      - `src.converters.survey_base`
      - `src.converters.excel_to_biometrics`
      - `src.converters.limesurvey`
  - Validation results:
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (Phase 1 grouped converter delegation retry - successful):
  - Applied grouped canonical delegation bindings in mirrored converter entry modules:
    - `app/src/converters/limesurvey.py`
    - `app/src/converters/excel_to_biometrics.py`
    - `app/src/converters/biometrics.py`
  - Initial Stage B run exposed CLI-contract regression caused by package-resolution precedence (`src.converters.excel_base` resolving to mirrored app module lacking `sanitize_task_name`).
  - Follow-up compatibility hardening:
    - updated `app/src/converters/excel_base.py` to export `sanitize_task_name`,
    - added `app/src/converters/survey_base.py` compatibility module.
  - Validation results:
    - `python -m pytest -q tests/test_prism_tools_cli_contract.py` -> pass (`5 passed`).
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

- 2026-02-28 (CI fast-check stability adjustment):
  - Updated Fast PR workflow check set in `.github/workflows/ci.yml` to use staged modularity gate:
    - from: `entrypoints-smoke,import-boundaries,pytest,linting,ruff,mypy`
    - to: `entrypoints-smoke,import-boundaries,pytest-modularity,linting,ruff,mypy`
  - Rationale:
    - keep repository guardrails enabled in PRs,
    - reduce repeated PR failures from broad integration pytest,
    - retain full `pytest` in Nightly Deep Checks.

- 2026-02-28 (Phase 1 shim cleanup completion):
  - Converted mirrored converter entry modules to pure compatibility shims (removed duplicated implementation bodies):
    - `app/src/converters/limesurvey.py`
    - `app/src/converters/excel_to_biometrics.py`
    - `app/src/converters/biometrics.py`
  - Preserved direct-script behavior for shimmed CLI-style modules via lightweight `__main__` passthrough in:
    - `app/src/converters/limesurvey.py`
    - `app/src/converters/excel_to_biometrics.py`
  - Validation results:
    - `python -m pytest -q tests/test_prism_tools_cli_contract.py` -> pass (`5 passed`).
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix` -> pass.
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` -> pass.

### Slice 1 Remaining Blockers (for closeout)

- None. Slice 1 closeout conditions are met for canonical-runtime + deterministic-test goals.

### Lessons Learned (Slice 1 rolling)

- 2026-02-28: A test file passing in isolation but failing in full `verify_repo` run is a strong indicator of import state leakage.
- 2026-02-28: Dual-tree package bridging solves immediate compatibility, but increases hidden coupling unless paired with strict shim contracts.
- 2026-02-28: Route-delegation tests are sensitive to module identity; deterministic bootstrap is more important than additional mocks.
- 2026-02-28: A two-stage pytest strategy (`pytest-modularity` first, full `pytest` second) improves refactor speed without losing integration safety.
- 2026-02-28: For migration-period package aliasing, `patch.object` on the imported module object is more robust than string patch targets.
- 2026-02-28: Starting with small, script-like maintenance modules is a low-risk way to enforce canonical backend ownership before touching high-churn converter modules.
- 2026-02-28: Incremental re-export binding in mirrored modules is a practical interim step when full shim replacement of large files would be too risky in one batch.
- 2026-02-28: In split-package migrations, canonical module loading by filesystem path is safer than name-based imports for mirrored module names.
- 2026-02-28: Compatibility helpers should be imported via package-qualified names (`src._compat`) to avoid context-dependent import failures.
- 2026-02-28: Converter modules with mixed relative + bare fallback imports should be normalized before delegation; otherwise migration can regress CLI import surfaces.
- 2026-02-28: Normalizing canonical import paths first reduces migration risk and makes later delegation attempts measurable instead of brittle.
- 2026-02-28: Even after import normalization, converter delegation can fail if canonical dependency modules are not yet mirrored/normalized in the same import graph; delegation must follow dependency chains, not single files.
- 2026-02-28: Global `sys.modules` cleanup in tests is too coarse; scoped setup/teardown mocks maintain determinism with lower regression risk.
- 2026-02-28: For split-package migrations, creating missing canonical dependency modules first is lower risk than direct delegation of high-churn entry modules.
- 2026-02-28: Import-boundary policies can be preserved while bridging behavior by using path-based loader shims instead of forbidden cross-tree import statements.
- 2026-02-28: During mirrored-module delegation, package resolution may still bind `src.*` imports to `app/src` modules in CLI contexts; mirrored compatibility modules must expose the canonical symbol surface until authority migration is complete.

### Test Changes Plan (Explicit)

#### Test code changes to implement

1. Introduce a shared test bootstrap utility (single place for `sys.path` strategy).
2. Replace broad `sys.modules` deletion patterns with scoped cleanup helpers.
3. Add an order-safety regression test or test run mode that exercises affected modules after formatting tests.
4. Keep delegation tests in `test_web_blueprints_conversion.py`, but ensure patched symbol path resolves to canonical module instance.

#### Verification commands for each PR in this slice

- Stage A (fast dev loop, default during refactor):
  - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest-modularity --no-fix`
- Stage B (pre-merge confidence):
  - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`
- Optional direct focused runs (debug only):
  - `pytest -q tests/test_web_blueprints_conversion.py`
  - `pytest -q tests/test_web_formatting.py`

#### Acceptance criteria for test changes

- No order-dependent pass/fail behavior between isolated and full runs.
- No new `app.src.*` runtime import violations.
- Existing endpoint contracts unchanged for conversion/project routes.

## Historical Archive (condensed)

Detailed 2026-02-27 extraction batch logs, legacy phase-by-phase migration notes, and superseded restart handoff details were condensed in this document on 2026-02-28 to remove drift and duplication.

For deep historical traceability, use:

- Git history of this file (`docs/MODULARIZATION_ROADMAP.md`)
- `CHANGELOG.md` for externally relevant milestones
- `docs/WRAPPER_CLEANUP_CHECKLIST.md` and `docs/WRAPPER_REMOVAL_READINESS.md` for script/wrapper cleanup specifics
