# Frontend Structural Assessment - Survey Generator (Phase 2.4)

Date: 2026-05-15

Scope:

- Survey Export page shell and merged-library browsing workflow
- Language/tool selection, template filtering, and selection-state orchestration
- Quick export and boilerplate generation workflows
- Handoff contract into Survey Customizer via session payload

Key files:

- [app/templates/survey_generator.html](app/templates/survey_generator.html)
- [app/static/js/survey-generator.js](app/static/js/survey-generator.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)
- [app/src/web/blueprints/tools_library_handlers.py](app/src/web/blueprints/tools_library_handlers.py)
- [app/src/web/blueprints/tools_generation_handlers.py](app/src/web/blueprints/tools_generation_handlers.py)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Open Survey Export page -> `/survey-generator`
- Load merged project/global template inventory -> `/api/list-library-files-merged`
- Quick export selected templates to LSS -> `/api/generate-lss`
- Generate methods boilerplate from selected templates -> `/api/generate-boilerplate`
- Transition to detailed customization flow -> `/survey-customizer` (session payload handoff)

Assessment note:

- Frontend owns selection UX, language/tool controls, filtering, and handoff payload assembly.
- Backend owns library resolution/merge semantics, export generation, and payload validation for generation endpoints.

## Current Stability Findings

### High - Library reload consistency depends on request-token + project-path matching

Affected:

- [app/static/js/survey-generator.js](app/static/js/survey-generator.js)
- [app/src/web/blueprints/tools_library_handlers.py](app/src/web/blueprints/tools_library_handlers.py)

Risk:

- If async library responses are applied after active project switches, users can export from stale library inventories.

Current guardrails:

- Frontend `libraryLoadToken` and project-path equality checks gate response application.
- Explicit `project_path` is included on merged-library requests.
- `prism-project-changed` event triggers immediate library reload.

### High - Survey Customizer handoff payload correctness is frontend-driven

Affected:

- [app/static/js/survey-generator.js](app/static/js/survey-generator.js)
- [app/static/js/survey-customizer.js](app/static/js/survey-customizer.js)

Risk:

- If session payload shape/version drifts, customizer may load stale/incomplete selection data or wrong project context.

Current guardrails:

- Canonical customizer state key with legacy-key cleanup.
- Payload includes `projectPath`, `savedAt`, and static asset version.
- Customizer performs TTL/version checks and rejects stale payloads.

## Runtime Smoke Checklist (Phase 2.4)

1. Load merged library for active project and verify source badges/counts reflect project/global availability.
2. Change active project and verify library list refreshes without stale rows from previous project.
3. Select templates with language constraints and verify language coverage warnings and button enablement logic.
4. Run Quick Export and verify LSS download succeeds with selected language/version options.
5. Run Customize & Export and verify customizer receives selected files, language set, and project path context.

## Remediation Slices

### Slice A - Library reload and source-resolution hardening

Acceptance:

- Stale library responses never mutate visible library state.
- Explicit `project_path` handling remains deterministic for explicit vs session fallback behavior.
- Section counts and selection states remain coherent after project switches.

Validation:

- Focused wiring assertions in [tests/test_survey_generator_workflow_wiring.py](tests/test_survey_generator_workflow_wiring.py).
- Focused merged-library path tests in [tests/test_survey_generator_library_paths.py](tests/test_survey_generator_library_paths.py).

### Slice B - Generation and customizer handoff contract hardening

Acceptance:

- Generation endpoints reject invalid payloads with clear error messages.
- Quick Export/Boilerplate payloads include only validated selected file paths.
- Customizer handoff payload remains schema-compatible and version-safe.

Validation:

- Focused generation handler tests in [tests/test_tools_generation_handlers.py](tests/test_tools_generation_handlers.py).
- Focused customizer handoff assertions in [tests/test_survey_customizer_workflow_wiring.py](tests/test_survey_customizer_workflow_wiring.py).

## Exit Criteria for Survey Generator Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
