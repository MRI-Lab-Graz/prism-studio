# Frontend Structural Assessment - Library and Library Editor (Phase 3.3)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- Survey Library manager page list/action wiring (checkout, submit, discard)
- Library Editor draft editing flow (simple editor and advanced JSON tab)
- Draft save endpoint contract and error handling behavior
- Backend survey-draft route ownership and manager delegation boundaries

Key files:

- [app/templates/library.html](app/templates/library.html)
- [app/static/js/library.js](app/static/js/library.js)
- [app/templates/library_editor.html](app/templates/library_editor.html)
- [app/src/web/blueprints/library.py](app/src/web/blueprints/library.py)

## Backend Command Ownership Map

Current ownership status: compliant; editor orchestration is now delegated to a dedicated frontend module.

Primary action -> backend command/endpoint mapping:

- Open survey library manager -> `/library`
- Open specific draft editor -> `/library/edit/<filename>`
- Checkout/create draft from master -> `/library/api/draft/<filename>` (POST)
- Discard draft -> `/library/api/draft/<filename>` (DELETE)
- Save draft content -> `/library/api/save/<filename>` (POST)
- Submit draft for review/publish flow -> `/library/api/publish/<filename>` (POST)

Assessment note:

- Backend blueprint owns all draft lifecycle execution and persistence.
- Frontend owns action orchestration, confirmations, and editor state transforms.

## Current Stability Findings

### High - Library Editor relied on large inline script and direct fetch path (resolved)

Affected:

- [app/templates/library_editor.html](app/templates/library_editor.html)
- [app/static/js/library_editor.js](app/static/js/library_editor.js)

Risk:

- Editor orchestration and save wiring were previously embedded inline, with direct fetch path usage.
- This increased maintenance risk and could diverge from packaged/fallback API behavior conventions used elsewhere.

Current guardrails:

- Runtime moved to [app/static/js/library_editor.js](app/static/js/library_editor.js) and save now uses shared relative-path fallback helper.
- Save success/failure feedback remains explicit and visible.
- Save action continues to go through backend draft API.

### High - External JSON editor CDN dependency in runtime-critical editing path (mitigated)

Affected:

- [app/templates/library_editor.html](app/templates/library_editor.html)

Risk:

- Editor depends on JSONEditor assets loaded from CDN; offline or restricted-network deployments can degrade advanced-edit capability.

Current guardrails:

- Simple editor path remains available in-page for common edits.
- Advanced editor sync rejects invalid JSON before switching back to simple mode.
- When JSONEditor assets are unavailable, advanced mode is explicitly disabled with a visible warning notice while save flow remains available in simple mode.

## Runtime Smoke Checklist (Phase 3.3)

1. Open Library page, run Checkout, Submit, and Discard actions, and verify table state refresh after each action.
2. Open a draft in Library Editor, edit metadata/question cards in simple mode, save, and verify backend draft content persists.
3. Switch between simple and advanced JSON tabs and verify sync logic preserves edits and blocks invalid JSON transitions.
4. Verify save errors surface clearly when backend returns non-success payload.
5. Validate action requests in packaged mode for relative path resolution and endpoint reachability.

## Remediation Slices

### Slice A - Extract editor inline logic into dedicated module with shared API fallback

Acceptance:

- `library_editor.html` uses a dedicated script module for editor orchestration.
- Draft save calls route through shared fallback helper (or equivalent common API adapter).

Validation:

- Add/extend workflow wiring assertions for extracted module and save endpoint usage.

### Slice B - Reduce runtime dependency risk for advanced JSON mode

Acceptance:

- Advanced mode remains available when CDN is unreachable via local fallback asset strategy or explicit graceful degrade messaging.
- User can still complete draft save flow without opaque failures.

Validation:

- Add focused regression assertions around advanced-mode availability/fallback behavior.

## Remediation Progress (2026-05-15)

- Slice A completed: `library_editor.html` now bootstraps a dedicated module (`app/static/js/library_editor.js`) and save calls route through `fetchWithRelativePathFallback`.
- Slice A validation completed: focused wiring checks in [tests/test_projects_workflow_wiring.py](tests/test_projects_workflow_wiring.py) and [tests/test_library_workflow_wiring.py](tests/test_library_workflow_wiring.py) are green.
- Slice B completed: advanced mode now degrades explicitly when JSONEditor assets are unavailable (disabled tab + visible guidance), while simple-mode editing/saving remains intact.
- Slice B validation completed: graceful-degrade wiring is asserted in [tests/test_projects_workflow_wiring.py](tests/test_projects_workflow_wiring.py).

## Exit Criteria for Library and Library Editor Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
