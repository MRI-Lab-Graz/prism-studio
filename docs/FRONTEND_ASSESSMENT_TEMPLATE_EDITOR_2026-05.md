# Frontend Structural Assessment - Template Editor (Phase 2.1)

Date: 2026-05-15

Scope:

- Template Editor page shell and source-selection workflow (project/global/new/import)
- Modality and schema switching with unsaved-change guardrails
- Validate/save/download/delete template lifecycle for project library ownership
- Template import pipelines (LSQ/LSG and generator-backed formats) and editor-state recovery paths

Key files:

- [app/templates/template_editor.html](app/templates/template_editor.html)
- [app/static/js/template-editor.js](app/static/js/template-editor.js)
- [app/static/js/template-editor/source-workflow.js](app/static/js/template-editor/source-workflow.js)
- [app/src/web/blueprints/tools_template_editor_blueprint.py](app/src/web/blueprints/tools_template_editor_blueprint.py)
- [app/src/web/blueprints/conversion_survey_handlers.py](app/src/web/blueprints/conversion_survey_handlers.py)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Open Template Editor shell -> `/template-editor`
- List merged project/global templates -> `/api/template-editor/list-merged`
- Create schema-backed blank template -> `/api/template-editor/new`
- Load template content -> `/api/template-editor/load`
- Validate current template payload -> `/api/template-editor/validate`
- Load schema for current modality/version -> `/api/template-editor/schema`
- Save editable project copy -> `/api/template-editor/save`
- Delete project template -> `/api/template-editor/delete`
- Download template JSON -> `/api/template-editor/download`
- Import LimeSurvey XML -> `/api/template-editor/import-lsq-lsg`
- Import tabular/archives via survey generator path -> `/api/survey-generate-templates`
- Export questionnaire document -> `/api/template-editor/export-questionnaire`

Assessment note:

- Frontend owns workflow orchestration, dirty-state prompts, and editor rendering.
- Backend owns schema validation, normalization, project-library path enforcement, import conversion, and persisted template state.

## Current Stability Findings

### High - Project-context and async request race surface remains complex across split modules

Affected:

- [app/static/js/template-editor.js](app/static/js/template-editor.js)
- [app/static/js/template-editor/source-workflow.js](app/static/js/template-editor/source-workflow.js)

Risk:

- Context-change and async refresh flows are spread across tracked select values, project-context request tokens, and multiple restore paths; regressions can detach editor state from active project context or misapply stale responses.

Current guardrails:

- Request-token invalidation and project-path equality checks before applying async responses.
- Explicit detached-draft fallback when project changes while project-bound template is loaded.
- Capture/restore editor snapshots on load/import/new failures.

### High - Save validity contract depends on frontend validation sequencing before backend save

Affected:

- [app/static/js/template-editor/source-workflow.js](app/static/js/template-editor/source-workflow.js)
- [app/src/web/blueprints/tools_template_editor_blueprint.py](app/src/web/blueprints/tools_template_editor_blueprint.py)

Risk:

- Frontend re-validates before save and then submits; backend also validates, but user-facing overwrite/fork messaging and filename normalization logic are split across client and server, increasing drift risk.

Current guardrails:

- Backend re-validates payload and blocks invalid writes.
- Backend enforces project-library-only save/delete scope.
- Frontend save decisions explicitly gate overwrite and readonly-fork paths.

## Runtime Smoke Checklist (Phase 2.1)

1. Load a project template, modify values, validate, save, and confirm list badges + filename state update correctly.
2. Load a readonly global template, save as project copy, and verify original global file remains unchanged.
3. Switch active project mid-session and verify detached-draft warning path plus disabled save until re-validation.
4. Import one LSQ/LSG source and one generator-backed source (CSV/XLSX/LSA), then validate and save successfully.
5. Trigger schema or modality switch with unsaved changes and verify cancel/revert keeps prior editor/select state intact.

## Remediation Slices

### Slice A - Project-context race hardening and state-recovery consolidation

Acceptance:

- One canonical context-guard contract for all async source-workflow operations.
- No stale async response can mutate editor state after project-context change.
- Failure recovery paths restore both editor content and selector state deterministically.

Validation:

- Focused wiring and context-switch assertions in [tests/test_template_editor_workflow_wiring.py](tests/test_template_editor_workflow_wiring.py).
- Focused save-path and project-scope tests in [tests/test_template_editor_save_paths.py](tests/test_template_editor_save_paths.py).

### Slice B - Save/import contract alignment across frontend and backend

Acceptance:

- Save path always targets `project/code/library/{modality}` for writable operations.
- Overwrite and readonly-fork decisions are explicit and consistent with backend conflict responses.
- Normalization and schema relaxations are preserved for approved import/copy scenarios only.

Validation:

- Focused save-path, software-validation, and variant-normalization suites:
  - [tests/test_template_editor_save_paths.py](tests/test_template_editor_save_paths.py)
  - [tests/test_template_editor_software_validation.py](tests/test_template_editor_software_validation.py)
  - [tests/test_template_editor_single_version_variantid.py](tests/test_template_editor_single_version_variantid.py)

## Exit Criteria for Template Editor Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
