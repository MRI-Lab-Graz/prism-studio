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

## Status Snapshot (2026-02-27)

- CLI modularization goals are operational in the repository (`app/src/cli/*` + command modules).
- Script reorganization is operational under `scripts/{ci,data,dev,maintenance,release,setup}`.
- Wrapper-cleanup policy docs exist and immediate cleanup has been executed.
- Frontend hardening slice for converter unsafe-pattern issues has reached a clean baseline.
- Remaining high-value work is decomposition of large Python modules in `app/src/`.

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

## Phase 6 — Python Monolith Decomposition (in progress)

Target scope:

- `app/src/converters/survey.py` (~4944 LOC)
- `app/src/web/blueprints/conversion.py` (~4124 LOC)
- `app/src/web/blueprints/tools.py` (~3453 LOC)
- `app/src/web/blueprints/projects.py` (~2877 LOC)

Objectives:

- Split monolithic files into domain-focused modules with stable public entrypoints.
- Preserve CLI/Web behavior exactly (no command, route, or API contract drift).
- Keep PRISM as a BIDS-compatible extension; do not alter BIDS-standard behavior.
- Improve testability by isolating orchestration from pure transformation/validation logic.

Execution slices:

1. Extract `survey.py` into smaller converter/service modules behind the same facade.
2. Extract Flask blueprint internals (`conversion`, `tools`, `projects`) into route + service layers.
3. Add/expand contract tests for CLI commands and critical web endpoints before each major move.
4. Validate each slice with targeted tests and repo checks before the next extraction.

Deliverables:

- Smaller Python modules with clear ownership boundaries.
- No functional regression in CLI and web conversion/validation workflows.
- Updated docs reflecting new module layout and contribution flow.

## Frontend Hardening Track (secondary, completed baseline)

- Converter unsafe-pattern hardening reached a clean baseline in repository checks.
- Further frontend cleanup can continue opportunistically, but it is no longer the roadmap driver.

## Progress Log

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
