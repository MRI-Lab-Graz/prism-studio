# Frontend Structural Assessment - PRISM App Runner (Phase 3.5)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- PRISM App Runner page shell, disabled-state rendering, and compatibility/run workflows
- Remote profile CRUD and Docker help/tag/pull orchestration from frontend
- Backend handler delegation and feature-flag disabled contract behavior
- Active-project binding for project-derived config/output paths

Key files:

- [app/templates/prism_app_runner.html](app/templates/prism_app_runner.html)
- [app/static/js/prism_app_runner.js](app/static/js/prism_app_runner.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)
- [app/src/web/blueprints/tools_prism_app_runner_handlers.py](app/src/web/blueprints/tools_prism_app_runner_handlers.py)

## Backend Command Ownership Map

Current ownership status: compliant with thin-web routing; backend owns compatibility and execution logic.

Primary action -> backend command/endpoint mapping:

- Open PRISM App Runner page -> `/prism-app-runner`
- Compatibility report -> `/api/prism-app-runner/compatibility` (POST)
- Prepare + run app -> `/api/prism-app-runner/run` (POST)
- Scan local images -> `/api/prism-app-runner/scan-images` (POST)
- Load app help/options -> `/api/prism-app-runner/load-help` (POST)
- Docker tag listing -> `/api/prism-app-runner/docker-tags` (POST)
- Docker pull -> `/api/prism-app-runner/docker-pull` (POST)
- Remote profile list/save -> `/api/prism-app-runner/remote-profiles` (GET/POST)
- Remote profile get/delete -> `/api/prism-app-runner/remote-profiles/<profile_name>` (GET/DELETE)

Assessment note:

- Frontend performs workflow orchestration and payload assembly.
- Backend handlers enforce project presence, runner/config checks, and run-time guardrails.

## Current Stability Findings

### High - Frontend included stale element references and mixed panel modes that could silently no-op (resolved)

Affected:

- [app/static/js/prism_app_runner.js](app/static/js/prism_app_runner.js)
- [app/templates/prism_app_runner.html](app/templates/prism_app_runner.html)

Risk:

- Script previously referenced optional/hidden controls (`runImageFolder`, `runLocalImage`, `scanImagesBtn`, `runOutputSubdir`) not present in the current template state.
- Optional chaining avoided hard crashes, but silent no-op behavior could mask workflow regressions.

Current guardrails:

- Stale control references and image-scan-only branches removed from [app/static/js/prism_app_runner.js](app/static/js/prism_app_runner.js).
- Browse handler now resolves picker kind explicitly from rendered control attributes and reports stable status text.
- Primary compatibility/run flow remains functional with required controls.

### High - Feature-disabled state relies on dual contract (HTML fieldset disable + API 503) (resolved)

Affected:

- [app/templates/prism_app_runner.html](app/templates/prism_app_runner.html)
- [app/src/web/blueprints/tools_prism_app_runner_handlers.py](app/src/web/blueprints/tools_prism_app_runner_handlers.py)

Risk:

- If frontend disabled rendering and backend feature flag handling diverge, user experience may degrade (enabled UI but API disabled, or opposite).

Current guardrails:

- Page handler always renders disabled-state context when feature flag is off.
- API handlers consistently return disabled payload/status when feature is off.
- Frontend script now detects disabled page state and blocks runtime actions consistently (including startup remote-profile bootstrap).
- Wiring and handler tests explicitly enforce this contract.

## Runtime Smoke Checklist (Phase 3.5)

1. Open page with no active project and verify compatibility checks still run while project-derived run actions remain safely constrained.
2. Open page with active project and verify derived paths update on app-name/project changes.
3. Exercise compatibility call, docker tags/help flow, and run request payload generation in dry-run mode.
4. Validate remote profile list/get/save/delete cycle and corresponding UI status behavior.
5. Validate feature-disabled mode renders proper warning and fieldset disable state while API routes return disabled responses.

## Remediation Slices

### Slice A - Remove or gate stale optional control references

Acceptance:

- Frontend references only rendered controls, or explicitly gates optional controls by template-driven feature flags.
- Silent no-op branches are reduced for maintainability.

Validation:

- Extend focused assertions in [tests/test_prism_app_runner_workflow_wiring.py](tests/test_prism_app_runner_workflow_wiring.py).

### Slice B - Keep disabled-state contract synchronized across template and handlers

Acceptance:

- Disabled HTML state and API disabled payload behavior stay in lockstep.
- Page render in disabled mode remains HTML-first (no disabled JSON page response).

Validation:

- Keep handler regression checks in [tests/test_prism_app_runner_page_handlers.py](tests/test_prism_app_runner_page_handlers.py).
- Keep wiring checks in [tests/test_prism_app_runner_workflow_wiring.py](tests/test_prism_app_runner_workflow_wiring.py).

## Remediation Progress (2026-05-15)

- Slice A completed: stale/non-rendered image control references and related no-op branches were removed from [app/static/js/prism_app_runner.js](app/static/js/prism_app_runner.js).
- Slice A validation completed: runner wiring assertions now explicitly guard against stale-control regressions in [tests/test_prism_app_runner_workflow_wiring.py](tests/test_prism_app_runner_workflow_wiring.py).
- Slice B completed: disabled-state frontend guards now align runtime behavior with disabled HTML/API contracts and suppress disabled-startup profile fetches.
- Slice B validation completed: [tests/test_prism_app_runner_workflow_wiring.py](tests/test_prism_app_runner_workflow_wiring.py) and [tests/test_prism_app_runner_page_handlers.py](tests/test_prism_app_runner_page_handlers.py) are green.

## Exit Criteria for PRISM App Runner Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
