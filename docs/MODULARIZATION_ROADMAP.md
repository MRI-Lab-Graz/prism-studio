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
- Full `pytest` in `verify_repo`: currently failing in `tests/test_web_blueprints_conversion.py` (6 failures) while the same file can pass in isolation.
- Interpretation: this is a **test-order/module-identity smell**, consistent with split import roots and compatibility indirection.

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

### Lessons Learned (Slice 1 rolling)

- 2026-02-28: A test file passing in isolation but failing in full `verify_repo` run is a strong indicator of import state leakage.
- 2026-02-28: Dual-tree package bridging solves immediate compatibility, but increases hidden coupling unless paired with strict shim contracts.
- 2026-02-28: Route-delegation tests are sensitive to module identity; deterministic bootstrap is more important than additional mocks.
- 2026-02-28: A two-stage pytest strategy (`pytest-modularity` first, full `pytest` second) improves refactor speed without losing integration safety.
- 2026-02-28: For migration-period package aliasing, `patch.object` on the imported module object is more robust than string patch targets.
- 2026-02-28: Starting with small, script-like maintenance modules is a low-risk way to enforce canonical backend ownership before touching high-churn converter modules.
- 2026-02-28: Incremental re-export binding in mirrored modules is a practical interim step when full shim replacement of large files would be too risky in one batch.

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

## Status Snapshot (2026-02-27)

- CLI modularization goals are operational in the repository (`app/src/cli/*` + command modules).
- Script reorganization is operational under `scripts/{ci,data,dev,maintenance,release,setup}`.
- Wrapper-cleanup policy docs exist and immediate cleanup has been executed.
- Frontend hardening slice for converter unsafe-pattern issues has reached a clean baseline.
- Remaining high-value work is decomposition of large Python modules in `app/src/`.

## Fresh Restart Handoff (2026-02-27)

Use this section to resume work quickly after a context reset.

### Current Architecture State

- Blueprint route-cluster splits completed:
  - `projects_library_blueprint.py` (project library/settings endpoints)
  - `tools_template_editor_blueprint.py` (template editor endpoints)
  - `conversion_participants_blueprint.py` (participants endpoints)
  - `conversion_survey_blueprint.py` (survey endpoint registration shim)
- `conversion.py` still contains the **survey handler implementations** (logic body), while survey routes are now registered from `conversion_survey_blueprint.py`.

### Last Verified Baseline

- Verification command: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`
- Status: passing at latest run on 2026-02-27.

### Next Exact Step

1. **Verify** functionality with `verify_repo.py` and existing tests. (Done: Handlers extracted)

### Resume Commands

- `source .venv/bin/activate`
- `pytest -q tests/test_prism_tools_cli_contract.py`
- `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

## Execution Track — Repository Modularity Hardening (2026-02-27)

This execution track operationalizes the architecture assessment into four points and enforces a strict loop:

1. modify,
2. validate using `tests/verify_repo.py` (targeted checks),
3. log result and lessons learned,
4. continue to next point.

### Point Checklist

- [x] **Point 1:** Canonical source direction (`app/src` authoritative, remove `app.src.*` cross-import patterns)
- [x] **Point 2:** Blueprint split preparation (route modules leaner, helper extraction from monolith blueprints)
- [x] **Point 3:** Service layer preparation (extract business-flow helpers out of route files)
- [x] **Point 4:** CI guardrails for import boundaries (fail fast on forbidden cross-tree imports)
- [x] **Point 5:** Survey Module Consolidation (Group ~25 files into ~6 domains) -> **Completed**
  - [x] LSA Domain
  - [x] IO Domain
  - [x] Templates Domain
  - [x] Processing Domain
  - [x] Participants Domain
  - [x] Core Domain (Base, Helpers, etc.)

### Validation Policy for this Track
### Validation Policy for this Track

- Use targeted verify checks after each point via:
  - `python tests/verify_repo.py --check entrypoints-smoke,path-hygiene,testing --no-fix`
- Run focused pytest suites for touched areas.
- Keep behavior and BIDS compatibility unchanged.

### Lessons Learned (rolling)

- 2026-02-27: Running `python tests/verify_repo.py --list-checks` first reduces accidental long-running checks and enables fast iteration.
- 2026-02-27: Import fallback chains across `src/` and `app/src/` are the primary source of modularity ambiguity; removing `app.src.*` imports is a low-risk, high-value first slice.
- 2026-02-27: Blueprint decomposition is safer when starting with pure helper extraction and compatibility aliases (no route signature changes).
- 2026-02-27: A dedicated boundary check in `verify_repo.py` gives immediate regression protection for architecture drift.
- 2026-02-27: With split `src/` and `app/src/` trees, deterministic test collection requires explicit package-path bridging to prevent import-order flakiness.
- 2026-02-27: A two-tier CI strategy (fast PR + nightly deep checks) gives better signal-to-noise than one monolithic pipeline.
- 2026-02-27: For giant Flask blueprints, extracting tightly scoped helper families (e.g., participant-filter + schema generation) in one move keeps call sites stable and simplifies verification.
- 2026-02-27: Citation/metadata parsing logic can be moved out of route modules without API changes when helper signatures stay identical.
- 2026-02-27: Blueprint decomposition can proceed safely by moving coherent route clusters (settings/library endpoints) into a dedicated blueprint and registering both during transition.
- 2026-02-27: Route-family blueprint extraction works best when grouped by UI domain (e.g., template-editor surface) so endpoint contracts remain unchanged while module ownership gets clearer.
- 2026-02-27: For conversion monoliths, participants-specific endpoints (`/api/participants*`, mapping save) form a stable extraction boundary with low coupling risk.
- 2026-02-27: Survey-route extraction can be staged by first splitting blueprint registration (`add_url_rule` shim) before deeper logic relocation, minimizing immediate regression risk.
- 2026-02-27: For large Flask blueprint slices, extracting handlers to a dedicated module and rebinding compatibility symbols in the legacy module allows safe incremental migration without endpoint drift.
- 2026-02-27: **Consolidation Pivot:** Moving from "many tiny files" to "few domain modules" (e.g. `survey_lsa.py`, `survey_io.py`) significantly improves navigating the codebase without losing separation of concerns.
- 2026-02-27: `sed` and strict grep checks are vital when refactoring module imports to ensure no dangling references to deleted files remain.

### Execution Progress (2026-02-27)

- Point 1 completed:
  - removed runtime `app.src.*` fallback imports in key modules under `src/` and `app/src/`
  - touched: `src/participants_converter.py`, `app/src/participants_converter.py`, `src/web/utils.py`, `src/converters/anc_export.py`, `src/batch_convert.py`
  - validation: `pytest -q tests/test_participants_mapping.py tests/test_web_formatting.py` (13 passed)
  - validation: `python tests/verify_repo.py --check entrypoints-smoke,path-hygiene,testing --no-fix` (pass; path-hygiene warnings are non-blocking)

- Point 2 completed:
  - extracted pure helpers from monolith blueprint into `app/src/web/blueprints/conversion_utils.py`
  - helpers extracted: filename normalization, official-library retry predicate, project library detection, task extraction
  - `app/src/web/blueprints/conversion.py` now consumes extracted helpers via compatibility aliases

- Point 3 completed:
  - created service layer package `app/src/web/services/`
  - extracted project session registration flow to `app/src/web/services/project_registration.py`
  - `conversion.py` now uses service-backed alias for `_register_session_in_project`

- Point 4 completed:
  - added `import-boundaries` check to `tests/verify_repo.py`
  - guardrail blocks runtime `app.src.*` imports inside `app/src` and `src`
  - validation: `python tests/verify_repo.py --check entrypoints-smoke,path-hygiene,testing,import-boundaries --no-fix` (pass; boundary check passed)

- Broad release-readiness sweep executed (user-requested):
  - `python tests/verify_repo.py --check pytest,linting,ruff,mypy --no-fix`
  - status: **not fully green** (stops at `pytest` check)
  - pytest blocker: existing import-layout mismatch in tests expecting `src.web.*` modules (`src.web.export_project`, `src.web.blueprints.projects`) that are not present in top-level `src/`
  - independent check results:
    - `linting`: not green (Black formatting check reports pending formatting)
    - `ruff`: green
    - `mypy`: not green (pre-existing type issues across app/src, src, vendor, scripts)

- Deterministic pytest-import setup implemented:
  - added symmetric package path bridging in `src/__init__.py` and `app/src/__init__.py` so mixed `src.*` imports can resolve across split trees
  - rerun: `python tests/verify_repo.py --check pytest --no-fix` → **passed**
  - rerun broad sweep: `python tests/verify_repo.py --check pytest,linting,ruff,mypy --no-fix`
    - `pytest`: green
    - `linting`: not green (Black formatting check)
    - `ruff`: green (confirmed in separate check)
    - `mypy`: not green (pre-existing repository type issues)

- Verification policy adjustment (requested):
  - relaxed `linting` to non-blocking warnings in `tests/verify_repo.py`
  - broad sweep now continues through `ruff` and `mypy` even when Black check reports formatting drift

- CI matrix added:
  - new workflow: `.github/workflows/ci.yml`
  - **Fast PR checks** (pull requests and non-scheduled pushes):
    - `entrypoints-smoke`, `import-boundaries`, `pytest`, `linting`, `ruff`, `mypy`
  - **Nightly deep checks** (scheduled + manual dispatch):
    - expanded repo health and security checks (`bids-compat-smoke`, `path-hygiene`, `python-security`, `unsafe-patterns`, `dependencies`, `pip-audit`, plus core quality checks)

- Fresh restart handoff next-step executed (survey logic relocation):
  - added dedicated survey handlers module: `app/src/web/blueprints/conversion_survey_handlers.py`
  - rewired survey blueprint imports to extracted module in `app/src/web/blueprints/conversion_survey_blueprint.py`
  - kept compatibility exports in `app/src/web/blueprints/conversion.py` by rebinding survey helper/handler symbols to extracted implementations
  - validation:
    - `pytest -q tests/test_web_formatting.py tests/test_web_anonymization.py tests/test_participants_mapping.py tests/test_projects_export_paths.py` (19 passed)
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` (pass)

- Legacy survey implementation bodies removed from `app/src/web/blueprints/conversion.py`; compact symbol exports now import from `conversion_survey_handlers`, with checks passing: `pytest -q tests/test_web_formatting.py tests/test_web_anonymization.py tests/test_participants_mapping.py tests/test_projects_export_paths.py` (19 passed) and `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` (pass).


- Phase 6 Python extraction slice (batch 31) completed:
  - extracted project export routes from `app/src/web/blueprints/projects.py`
  - new module: `app/src/web/blueprints/projects_export_blueprint.py`
  - moved routes: `/api/projects/export`, `/api/projects/anc-export`
  - setup deprecation in `projects.py` forwarding to the new module, and wired registration in `app/prism-studio.py`
- Post-extraction validation:
  - targeted export tests passed: `pytest -q tests/test_projects_export_paths.py tests/test_projects_export_mapping_exclusion.py` (`5 passed`)
  - repo checks passed: `python tests/verify_repo.py --check import-boundaries,pytest --no-fix`

- Phase 6 Pivot: Survey Module Consolidation (IO & LSA):
  - Consolidated 5 LSA submodules (`analysis`, `metadata`, `participants`, `preprocess`, `unmatched`) into a single **`app/src/converters/survey_lsa.py`**.
  - Consolidated 3 IO submodules (`response_writing`, `sidecars`, `preview`) into a single **`app/src/converters/survey_io.py`**.
  - Updated `survey.py` imports to use the new domain modules.
  - Deleted 8 fragmented files.
  - Validation: `pytest -q tests/test_prism_tools_cli_contract.py` passed (5/5).
  - Validation: Runtime import check passed.

- Use targeted verify checks after each point via:
  - `python tests/verify_repo.py --check entrypoints-smoke,path-hygiene,testing --no-fix`
- Run focused pytest suites for touched areas.
- Keep behavior and BIDS compatibility unchanged.

### Lessons Learned (rolling)

- 2026-02-27: Running `python tests/verify_repo.py --list-checks` first reduces accidental long-running checks and enables fast iteration.
- 2026-02-27: Import fallback chains across `src/` and `app/src/` are the primary source of modularity ambiguity; removing `app.src.*` imports is a low-risk, high-value first slice.
- 2026-02-27: Blueprint decomposition is safer when starting with pure helper extraction and compatibility aliases (no route signature changes).
- 2026-02-27: A dedicated boundary check in `verify_repo.py` gives immediate regression protection for architecture drift.
- 2026-02-27: With split `src/` and `app/src/` trees, deterministic test collection requires explicit package-path bridging to prevent import-order flakiness.
- 2026-02-27: A two-tier CI strategy (fast PR + nightly deep checks) gives better signal-to-noise than one monolithic pipeline.
- 2026-02-27: For giant Flask blueprints, extracting tightly scoped helper families (e.g., participant-filter + schema generation) in one move keeps call sites stable and simplifies verification.
- 2026-02-27: Citation/metadata parsing logic can be moved out of route modules without API changes when helper signatures stay identical.
- 2026-02-27: Blueprint decomposition can proceed safely by moving coherent route clusters (settings/library endpoints) into a dedicated blueprint and registering both during transition.
- 2026-02-27: Route-family blueprint extraction works best when grouped by UI domain (e.g., template-editor surface) so endpoint contracts remain unchanged while module ownership gets clearer.
- 2026-02-27: For conversion monoliths, participants-specific endpoints (`/api/participants*`, mapping save) form a stable extraction boundary with low coupling risk.
- 2026-02-27: Survey-route extraction can be staged by first splitting blueprint registration (`add_url_rule` shim) before deeper logic relocation, minimizing immediate regression risk.
- 2026-02-27: For large Flask blueprint slices, extracting handlers to a dedicated module and rebinding compatibility symbols in the legacy module allows safe incremental migration without endpoint drift.

### Execution Progress (2026-02-27)

- Point 1 completed:
  - removed runtime `app.src.*` fallback imports in key modules under `src/` and `app/src/`
  - touched: `src/participants_converter.py`, `app/src/participants_converter.py`, `src/web/utils.py`, `src/converters/anc_export.py`, `src/batch_convert.py`
  - validation: `pytest -q tests/test_participants_mapping.py tests/test_web_formatting.py` (13 passed)
  - validation: `python tests/verify_repo.py --check entrypoints-smoke,path-hygiene,testing --no-fix` (pass; path-hygiene warnings are non-blocking)

- Point 2 completed:
  - extracted pure helpers from monolith blueprint into `app/src/web/blueprints/conversion_utils.py`
  - helpers extracted: filename normalization, official-library retry predicate, project library detection, task extraction
  - `app/src/web/blueprints/conversion.py` now consumes extracted helpers via compatibility aliases

- Point 3 completed:
  - created service layer package `app/src/web/services/`
  - extracted project session registration flow to `app/src/web/services/project_registration.py`
  - `conversion.py` now uses service-backed alias for `_register_session_in_project`

- Point 4 completed:
  - added `import-boundaries` check to `tests/verify_repo.py`
  - guardrail blocks runtime `app.src.*` imports inside `app/src` and `src`
  - validation: `python tests/verify_repo.py --check entrypoints-smoke,path-hygiene,testing,import-boundaries --no-fix` (pass; boundary check passed)

- Broad release-readiness sweep executed (user-requested):
  - `python tests/verify_repo.py --check pytest,linting,ruff,mypy --no-fix`
  - status: **not fully green** (stops at `pytest` check)
  - pytest blocker: existing import-layout mismatch in tests expecting `src.web.*` modules (`src.web.export_project`, `src.web.blueprints.projects`) that are not present in top-level `src/`
  - independent check results:
    - `linting`: not green (Black formatting check reports pending formatting)
    - `ruff`: green
    - `mypy`: not green (pre-existing type issues across app/src, src, vendor, scripts)

- Deterministic pytest-import setup implemented:
  - added symmetric package path bridging in `src/__init__.py` and `app/src/__init__.py` so mixed `src.*` imports can resolve across split trees
  - rerun: `python tests/verify_repo.py --check pytest --no-fix` → **passed**
  - rerun broad sweep: `python tests/verify_repo.py --check pytest,linting,ruff,mypy --no-fix`
    - `pytest`: green
    - `linting`: not green (Black formatting check)
    - `ruff`: green (confirmed in separate check)
    - `mypy`: not green (pre-existing repository type issues)

- Verification policy adjustment (requested):
  - relaxed `linting` to non-blocking warnings in `tests/verify_repo.py`
  - broad sweep now continues through `ruff` and `mypy` even when Black check reports formatting drift

- CI matrix added:
  - new workflow: `.github/workflows/ci.yml`
  - **Fast PR checks** (pull requests and non-scheduled pushes):
    - `entrypoints-smoke`, `import-boundaries`, `pytest`, `linting`, `ruff`, `mypy`
  - **Nightly deep checks** (scheduled + manual dispatch):
    - expanded repo health and security checks (`bids-compat-smoke`, `path-hygiene`, `python-security`, `unsafe-patterns`, `dependencies`, `pip-audit`, plus core quality checks)

- Fresh restart handoff next-step executed (survey logic relocation):
  - added dedicated survey handlers module: `app/src/web/blueprints/conversion_survey_handlers.py`
  - rewired survey blueprint imports to extracted module in `app/src/web/blueprints/conversion_survey_blueprint.py`
  - kept compatibility exports in `app/src/web/blueprints/conversion.py` by rebinding survey helper/handler symbols to extracted implementations
  - validation:
    - `pytest -q tests/test_web_formatting.py tests/test_web_anonymization.py tests/test_participants_mapping.py tests/test_projects_export_paths.py` (19 passed)
    - `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` (pass)

- Legacy survey implementation bodies removed from `app/src/web/blueprints/conversion.py`; compact symbol exports now import from `conversion_survey_handlers`, with checks passing: `pytest -q tests/test_web_formatting.py tests/test_web_anonymization.py tests/test_participants_mapping.py tests/test_projects_export_paths.py` (19 passed) and `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix` (pass).


- Phase 6 Python extraction slice (batch 31) completed:
  - extracted project export routes from `app/src/web/blueprints/projects.py`
  - new module: `app/src/web/blueprints/projects_export_blueprint.py`
  - moved routes: `/api/projects/export`, `/api/projects/anc-export`
  - setup deprecation in `projects.py` forwarding to the new module, and wired registration in `app/prism-studio.py`
- Post-extraction validation:
  - targeted export tests passed: `pytest -q tests/test_projects_export_paths.py tests/test_projects_export_mapping_exclusion.py` (`5 passed`)
  - repo checks passed: `python tests/verify_repo.py --check import-boundaries,pytest --no-fix`


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

## Phase 3 — Incremental Extraction (completed)

Recommended order (lowest risk first):

1. `library` + `dataset` handlers ✅
2. `convert` + `anonymize` handlers ✅
3. `biometrics` handlers ✅
4. `survey` handlers ✅
5. `recipes` handlers ✅

After each extraction:
- Run contract tests + targeted functional tests.
- Keep old import paths working until migration is complete.

## Phase 4 — Script Reorganization (completed)

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

## Phase 5 — Cleanup and Hardening (completed)

- Remove temporary wrappers after one release cycle.
- Add import boundary checks (no command module reaches unrelated domains).
- Update developer docs for new layout and contribution flow.
- Follow `docs/WRAPPER_CLEANUP_CHECKLIST.md` for deterministic wrapper retirement.

## Phase 6 — Python Monolith Decomposition (Pivoting: Consolidation)

Target scope:

- `app/src/converters/survey.py` (and its ~25 submodules)
- Refactor strategy changed from "Extract Everything" to "Consolidate into Domains".

Objectives:

- Reduce file count from ~26 to ~6-8 key domain modules.
- Maintain the benefits of separation (no monolithic file) but reduce navigation complexity.
- Groups:
    1. **Core**: `survey.py` (Facade), `survey_types.py`
    2. **Participants**: `survey_participants.py` (merge mapping, id_resolution, etc.)
    3. **LSA**: `survey_lsa.py` (merge all 8+ `lsa_*.py` files)
    4. **IO**: `survey_io.py` (merge reading/writing/sidecars)
    5. **Templates**: `survey_templates.py` (merge loading, global, assignment)
    6. **Processing**: `survey_processing.py` (merge row_processing, value_normalization, columns)

Execution slices:

1. Consolidate **LSA** modules (highest fragmentation).
2. Consolidate **IO** modules.
3. Consolidate **Template** modules.
4. Consolidate **participant/processing** modules.

Deliverables:

- A manageable set of ~8 files for survey conversion.
- No functional regression.

## Frontend Hardening Track (secondary, completed baseline)

- Converter unsafe-pattern hardening reached a clean baseline in repository checks.
- Further frontend cleanup can continue opportunistically, but it is no longer the roadmap driver.

## Progress Log

- Phase 6 Python extraction slice (batch 30) completed:
  - extracted conversion survey route cluster registration into dedicated blueprint module
  - new module: `app/src/web/blueprints/conversion_survey_blueprint.py`
  - moved route registration for: `/api/survey-languages`, `/api/survey-convert-preview`, `/api/survey-convert`, `/api/survey-convert-validate`, `/api/save-unmatched-template`
  - detached corresponding route decorators from `app/src/web/blueprints/conversion.py` and registered `conversion_survey_bp` in `app/prism-studio.py`
- Post-extraction validation:
  - targeted web/conversion-adjacent tests passed: `pytest -q tests/test_web_formatting.py tests/test_web_anonymization.py tests/test_participants_mapping.py tests/test_projects_export_paths.py` (`19 passed`)
  - repo checks passed: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

- Phase 6 Python extraction slice (batch 29) completed:
  - performed blueprint-level split for conversion participants route cluster from `app/src/web/blueprints/conversion.py`
  - new module: `app/src/web/blueprints/conversion_participants_blueprint.py`
  - moved routes: `/api/save-participant-mapping`, `/api/participants-check`, `/api/participants-detect-id`, `/api/participants-preview`, `/api/participants-convert`
  - wired blueprint registration in `app/prism-studio.py` and removed moved handlers from `conversion.py`
- Post-extraction validation:
  - targeted participants/web tests passed: `pytest -q tests/test_participants_mapping.py tests/test_web_anonymization.py tests/test_web_formatting.py` (`16 passed`)
  - repo checks passed: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

- Phase 6 Python extraction slice (batch 28) completed:
  - performed blueprint-level split for template-editor route cluster from `app/src/web/blueprints/tools.py`
  - new module: `app/src/web/blueprints/tools_template_editor_blueprint.py`
  - moved routes: `/template-editor` and all `/api/template-editor/*` endpoints
  - wired blueprint registration in `app/prism-studio.py` and removed moved handlers from `tools.py`
- Post-extraction validation:
  - targeted web/projects tests passed: `pytest -q tests/test_web_anonymization.py tests/test_web_formatting.py tests/test_projects_export_paths.py tests/test_projects_export_mapping_exclusion.py` (`20 passed`)
  - repo checks passed: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

- Phase 6 Python extraction slice (batch 27) completed:
  - performed blueprint-level split for project library/settings route cluster
  - new module: `app/src/web/blueprints/projects_library_blueprint.py`
  - moved routes: `/api/projects/modalities`, `/api/settings/global-library` (GET/POST), `/api/projects/library-path`
  - wired new blueprint registration in `app/prism-studio.py` and removed moved handlers from `app/src/web/blueprints/projects.py`
- Post-extraction validation:
  - targeted projects/web tests passed: `pytest -q tests/test_projects_export_paths.py tests/test_projects_export_mapping_exclusion.py tests/test_web_formatting.py` (`17 passed`)
  - repo checks passed: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

- Phase 6 Python extraction slice (batch 26) completed:
  - extracted recruitment validation and CITATION.cff parsing/merge helpers from `app/src/web/blueprints/projects.py`
  - new module: `app/src/web/blueprints/projects_citation_helpers.py`
  - preserved compatibility via direct helper imports in `projects.py` with no route/API signature changes
- Post-extraction validation:
  - targeted projects/web tests passed: `pytest -q tests/test_projects_export_paths.py tests/test_projects_export_mapping_exclusion.py tests/test_web_formatting.py` (`17 passed`)
  - repo checks passed: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

- Phase 6 Python extraction slice (batch 25) completed:
  - extracted participant-filtering and NeuroBagel participant-schema helpers from `app/src/web/blueprints/conversion.py`
  - new module: `app/src/web/blueprints/conversion_participants_helpers.py`
  - preserved compatibility by importing helpers into `conversion.py` without route/API contract changes
- Post-extraction validation:
  - targeted web/participants tests passed: `pytest -q tests/test_web_formatting.py tests/test_web_anonymization.py tests/test_participants_mapping.py` (`16 passed`)
  - repo checks passed: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`

- Phase 6 Python extraction slice (batch 24) completed:
  - extracted ID/session column resolution helper from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_id_resolution.py`
  - preserved compatibility via wrapper delegation in `survey.py`
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - ID-resolution helper smoke-check passed (`_resolve_id_and_session_cols`)

- Phase 6 Python extraction slice (batch 23) completed:
  - extracted item-value normalization helper from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_value_normalization.py`
  - preserved compatibility via wrapper delegation in `survey.py`
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - value-normalization helper smoke-check passed (`_normalize_item_value`)

- Phase 6 Python extraction slice (batch 22) completed:
  - extracted LSA read-result unpacking and language/strict-level preprocessing blocks from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_lsa_preprocess.py`
  - preserved compatibility by delegating through existing LSA conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - LSA preprocess helper smoke-check passed (`_unpack_lsa_read_result`, `_resolve_lsa_language_and_strict`)

- Phase 6 Python extraction slice (batch 21) completed:
  - extracted subject ID-mapping application block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_id_mapping.py`
  - preserved compatibility by delegating through existing conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - ID-mapping helper smoke-check passed (`_apply_subject_id_mapping`)

- Phase 6 Python extraction slice (batch 20) completed:
  - extracted response-writing loop and tolerance-warning summary block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_response_writing.py`
  - preserved compatibility by delegating through existing conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - response-writing helper smoke-check passed (`_process_and_write_responses`, `_build_tolerance_warnings`)

- Phase 6 Python extraction slice (batch 19) completed:
  - extracted task-sidecar writing block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_sidecars.py`
  - preserved compatibility by delegating through existing conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - sidecar helper smoke-check passed (`_write_task_sidecars`)

- Phase 6 Python extraction slice (batch 18) completed:
  - extracted mapping/result-preparation block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_mapping_results.py`
  - preserved compatibility by delegating through existing conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - mapping-results helper smoke-check passed (`_resolve_tasks_with_warnings`, `_build_col_to_task_and_task_runs`, `_build_template_matches_payload`)

- Phase 6 Python extraction slice (batch 17) completed:
  - extracted session detection/filtering and duplicate-ID handling blocks from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_session_handling.py`
  - preserved compatibility by delegating through existing conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - session-handling helper smoke-check passed (`_detect_sessions`, `_filter_rows_by_selected_session`, `_handle_duplicate_ids`)

- Phase 6 Python extraction slice (batch 16) completed:
  - extracted survey-filter parsing/validation block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_selection.py`
  - preserved compatibility by delegating to helper from existing flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - selection helper smoke-check passed (`_resolve_selected_tasks`)

- Phase 6 Python extraction slice (batch 15) completed:
  - extracted LSA participant-column registration and rename-derivation blocks from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_lsa_participants.py`
  - preserved compatibility by delegating to helpers from existing flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - import smoke-check passed for extracted LSA participant helpers

- Phase 6 Python extraction slice (batch 14) completed:
  - extracted unmatched LSA group normalization/aggregation block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_lsa_unmatched.py`
  - preserved compatibility by delegating from the existing conversion flow
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)
  - import smoke-check passed for `survey_lsa_unmatched` helper and survey conversion entrypoint

- Phase 6 Python extraction slice (batch 13) completed:
  - extracted LSA structure-analysis helper from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_lsa_analysis.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
  - resolved circular-import risk by using lazy imports inside extracted helper
- Post-extraction validation:
  - LSA helper wiring smoke-check passed (`_analyze_lsa_structure`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 12) completed:
  - extracted template-copy and LSA template-assignment helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_template_assignment.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
- Post-extraction validation:
  - template-assignment helper wiring smoke-check passed (`_copy_templates_to_project`, `_add_matched_template`, `_add_generated_template`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 11) completed:
  - extracted global template discovery/comparison helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_global_templates.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
- Post-extraction validation:
  - global helper wiring smoke-check passed (`_load_global_library_path`, `_load_global_templates`, `_find_matching_global_template`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 10) completed:
  - extracted template-loading/preprocessing helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_template_loading.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
- Post-extraction validation:
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 9) completed:
  - extracted row-processing/validation helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_row_processing.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
- Post-extraction validation:
  - row helper wiring smoke-check passed (`_process_survey_row`, `_process_survey_row_with_run`, `_validate_survey_item_value`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 8) completed:
  - extracted preview-generation helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_preview.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
- Post-extraction validation:
  - preview helper wiring smoke-check passed (`_generate_participants_preview`, `_generate_dry_run_preview`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 7) completed:
  - extracted LimeSurvey metadata inference helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_lsa_metadata.py`
  - preserved compatibility using thin wrapper delegation in `survey.py`
- Post-extraction validation:
  - wrapper smoke-check passed (`infer_lsa_metadata`, `_infer_lsa_language_and_tech` fallback behavior)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 6) completed:
  - extracted missing-token/technical-override helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_technical.py`
  - preserved compatibility by importing helper symbols back into `survey.py`
- Post-extraction validation:
  - technical helper smoke-check passed (`_inject_missing_token`, `_apply_technical_overrides`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 5) completed:
  - extracted alias/canonicalization helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_aliases.py`
  - preserved compatibility by importing helper symbols back into `survey.py`
- Post-extraction validation:
  - alias helper smoke-check passed (alias row parsing + dataframe alias remapping)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 4) completed:
  - extracted i18n/localization helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_i18n.py`
  - preserved compatibility by importing helper symbols back into `survey.py`
- Post-extraction validation:
  - i18n helper smoke-check passed (`_normalize_language`, `_localize_survey_template`)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 3) completed:
  - extracted participant mapping/template helper block from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_participants.py`
  - preserved compatibility by importing helper symbols back into `survey.py`
  - added explicit compatibility re-export tuple in `survey.py` to avoid drift during migration
- Post-extraction validation:
  - participant helper smoke-check passed (`_is_participant_template`, mapping/template helpers)
  - downstream import compatibility check passed (`template_matcher` path)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 2) completed:
  - extracted template-structure and survey-filename/run helpers from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_helpers.py`
  - preserved compatibility by importing extracted helper symbols back into `survey.py`
- Post-extraction validation:
  - helper smoke-check passed (template structure extraction + filename/run helpers)
  - downstream import compatibility check passed (`template_matcher` import path)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Phase 6 Python extraction slice (batch 1) completed:
  - extracted survey column/run parsing helpers from `app/src/converters/survey.py`
  - new module: `app/src/converters/survey_columns.py`
  - preserved compatibility by importing extracted helper symbols back into `survey.py`
- Post-extraction validation:
  - helper smoke-check passed (run parsing + LimeSurvey column extraction)
  - CLI contract tests passed: `pytest tests/test_prism_tools_cli_contract.py -q` (`5 passed`)

- Frontend hardening slice (batch 1) completed in `app/static/js/modules/converter/survey-convert.js`:
  - replaced selected dynamic `innerHTML` render paths with explicit DOM construction in template-match and question-card UI blocks
  - preserved existing UI behavior while removing unsafe pattern triggers in those paths
- Re-ran safety check after patch batch:
  - `source .venv/bin/activate && python tests/verify_repo.py . --no-fix --check unsafe-patterns`
  - result: **No obvious unsafe patterns found**
  - report: `prism-studio_report_2026-02-27_07-04-52.txt`

- Phase 6 (Python monolith decomposition) target sizing snapshot captured:
  - `app/src/converters/survey.py` (~4944 LOC)
  - `app/src/web/blueprints/conversion.py` (~4124 LOC)
  - `app/src/web/blueprints/tools.py` (~3453 LOC)
  - `app/src/web/blueprints/projects.py` (~2877 LOC)

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
- Moved CI helper scripts with wrappers:
  - `scripts/ci/test_bids_compliance.py`
  - `scripts/ci/test_sav_anonymization.py`
- Moved additional release/CI scripts with wrappers:
  - `scripts/release/bundle_pyedflib.py`
  - `scripts/ci/test_pyedflib.sh`
  - `scripts/ci/test_pyedflib.bat`
- Moved remaining root scripts with wrappers:
  - `scripts/data/anonymize_sav_files.py`
  - `scripts/setup/windows_workshop_preflight.ps1`
  - `scripts/ci/test_participants_mapping.py`
- Updated selected docs/comments to canonical script paths while retaining old-path wrappers:
  - vendor pyedflib docs now reference `scripts/ci/*` and `scripts/release/*`
- Completed a broader canonical-path migration pass for moved scripts:
  - BIDS docs now reference `scripts/ci/test_bids_compliance.py`
  - CLI/environment examples now reference `scripts/data/*`
  - moved data scripts now advertise canonical invocation paths in their usage headers
- Audited non-doc automation hooks (workflows/config/helper surfaces) for legacy root-script paths; no remaining references found for moved scripts.
- Added wrapper retirement playbook in `docs/WRAPPER_CLEANUP_CHECKLIST.md` with explicit exit criteria, removal steps, and rollback plan.
- Added import-boundary tests for CLI command modules:
  - `tests/test_cli_command_import_boundaries.py`
  - forbids command-module imports of `src.cli.commands.*` and CLI wiring modules (`dispatch`, `parser`, `entrypoint`)
  - forbids relative imports in command modules to keep boundaries explicit
- Added release-note coverage in `CHANGELOG.md` for canonical script paths and wrapper grace-period policy.
- Added wrapper-removal readiness gate report in `docs/WRAPPER_REMOVAL_READINESS.md` with current go/no-go status and trigger conditions.
- Executed immediate wrapper cleanup (user-directed):
  - removed legacy root-level script wrappers
  - standardized script execution on canonical paths in `scripts/{ci,data,dev,maintenance,release,setup}`
  - moved setup test utilities to `scripts/ci/` with setup-path compatibility wrappers
  - updated changelog + readiness/checklist docs to reflect completed cleanup

## Learned Lessons

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
- When moving scripts, replace location-dependent path logic with repo-root relative resolution to keep wrappers and canonical paths consistent.
- Keep platform-specific wrappers minimal and native (`.sh` exec, `.bat` call) so behavior remains predictable across OSes.
- Workshop/platform utility scripts fit best under `scripts/setup/`; keeping root path wrappers avoids breaking onboarding documentation.
- Canonical-path doc updates can happen incrementally right after each move as long as wrappers remain available.
- A single regex scan over all moved root scripts is an efficient way to catch remaining stale path references after each reorg batch.
- Separating path-audit scans into docs and non-doc automation scopes makes it easy to confirm migration completeness without unnecessary edits.
- Wrapper deletion is safer when gated by explicit release-cycle, reference-scan, and rollback criteria documented up front.
- AST-based import boundary tests provide a low-cost guardrail against cross-domain coupling regressions.
- Declaring migration policy in changelog early reduces ambiguity for downstream users and automation maintainers.
- Explicit go/no-go readiness reporting prevents premature wrapper deletion and keeps cleanup decisions auditable.
- When cleanup timing changes, update policy docs first and record the override decision explicitly to keep migration history coherent.
- For web modules, prioritize replacing dynamic `innerHTML` first; static UI strings can be handled in later passes.
- Security hardening is safest when done in narrow slices with verification after each slice.

## Immediate next step

- Start Phase 6 with `app/src/converters/survey.py` extraction into smaller modules while preserving current external behavior.
- Add/lock targeted contract tests for survey conversion entrypoints before and after each extraction slice.
- Keep changelog/roadmap entries aligned with each completed Python modularization slice.
