# Frontend Structural Assessment - Survey Customizer (Phase 2.3)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- Survey Customizer page shell and session-state hydration from Survey Generator
- Group/question organization workflows (reorder, mandatory toggles, include/exclude, matrix grouping)
- Export configuration and LimeSurvey settings serialization
- Project-bound template copy behavior during export (`saveToProject`)

Key files:

- [app/templates/survey_customizer.html](app/templates/survey_customizer.html)
- [app/static/js/survey-customizer.js](app/static/js/survey-customizer.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)
- [app/src/web/blueprints/tools_survey_customizer_handlers.py](app/src/web/blueprints/tools_survey_customizer_handlers.py)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Open Survey Customizer page -> `/survey-customizer`
- Load grouped survey customization payload from selected templates -> `/api/survey-customizer/load`
- Export customized survey to LSS and optionally copy templates to project library -> `/api/survey-customizer/export`
- Load export-format capabilities/options -> `/api/survey-customizer/formats`

Assessment note:

- Frontend owns customization UX state orchestration and tool-setting interactions.
- Backend owns template parsing, grouped-question payload creation, export generation, and project-path enforcement for template copying.

## Current Stability Findings

### High - Session-state hydration contract is migration-aware but has multiple fallback paths

Affected:

- [app/static/js/survey-customizer.js](app/static/js/survey-customizer.js)

Risk:

- State restoration depends on legacy/new storage keys, TTL checks, and asset-version matching; drift in these guards can cause stale or incompatible customizer state to load silently.

Current guardrails:

- Canonical key migration from legacy storage keys.
- TTL expiration and static-asset-version mismatch invalidation.
- Explicit no-data fallback with guided return path to Survey Generator.

### High - Project-bound export-copy behavior requires strict active-project/source-project alignment

Affected:

- [app/static/js/survey-customizer.js](app/static/js/survey-customizer.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)
- [app/src/web/blueprints/tools_survey_customizer_handlers.py](app/src/web/blueprints/tools_survey_customizer_handlers.py)

Risk:

- If active project changes after customizer load, exporting with `saveToProject` can target the wrong project unless source/active path checks remain consistent on both client and server.

Current guardrails:

- Frontend disables `saveToProject` when active project differs from loaded source project.
- Export payload sends explicit `project_path`.
- Backend route prioritizes explicit `project_path` and handler validates existing project root before copy.

## Runtime Smoke Checklist (Phase 2.3)

1. Enter Customizer from Survey Generator with selected files and verify groups/questions hydrate correctly.
2. Reorder groups/questions, toggle mandatory/include flags, and verify matrix grouping behavior matches export options.
3. Change active project after load and verify `saveToProject` disables with clear guidance.
4. Export LSS with `saveToProject` enabled from a valid active project and confirm template copies land in `code/library/survey/`.
5. Trigger stale/no-state entry path and verify warning + navigation path back to Survey Generator.

## Remediation Slices

### Slice A - State hydration and stale-session resilience hardening

Acceptance:

- Legacy/new session key migrations always converge to one canonical payload.
- Expired or incompatible stored payloads are rejected deterministically.
- No stale session payload can silently override fresh export selections.

Validation:

- Focused workflow wiring assertions in [tests/test_survey_customizer_workflow_wiring.py](tests/test_survey_customizer_workflow_wiring.py).
- Add focused session-state regression checks for TTL and version-mismatch paths.

### Slice B - Project-bound export copy contract hardening

Acceptance:

- `saveToProject` copy operations only target the validated active project context.
- Stale/missing project paths are rejected with actionable errors.
- Template copies never fall back to legacy root paths.

Validation:

- Focused project-copy path tests in [tests/test_project_template_write_paths.py](tests/test_project_template_write_paths.py).
- Focused survey customizer wiring assertions in [tests/test_survey_customizer_workflow_wiring.py](tests/test_survey_customizer_workflow_wiring.py).

## Exit Criteria for Survey Customizer Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
