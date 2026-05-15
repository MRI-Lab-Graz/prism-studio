# Frontend Structural Assessment - Results (Phase 1.4)

Date: 2026-05-15

Scope:

- Results page shell and summary/issue-group rendering UX
- Re-validation mode selection and re-validation start flow
- Re-validation progress polling, completion redirect, and error recovery
- Result action controls (download, cleanup, validate another) during active re-validation

Key files:

- [app/templates/results.html](app/templates/results.html)
- [app/static/js/results.js](app/static/js/results.js)
- [app/static/css/results.css](app/static/css/results.css)
- [app/src/web/blueprints/validation.py](app/src/web/blueprints/validation.py)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Display selected validation result -> `/results/<result_id>`
- Start re-validation job -> `/revalidate/<result_id>`
- Poll re-validation job progress -> `/api/progress/<job_id>`
- Download report payload -> `/download_report/<result_id>`
- Cleanup stored result/temp artifacts -> `/cleanup/<result_id>`

Assessment note:

- Frontend owns result rendering, action-state gating, and progress UX.
- Backend owns re-validation execution, progress state truth, result generation, and retention/cleanup behavior.

## Current Stability Findings

### High - Re-validation progress polling has no explicit abort/cancel contract

Affected:

- [app/static/js/results.js](app/static/js/results.js)
- [app/src/web/blueprints/validation.py](app/src/web/blueprints/validation.py)

Risk:

- Polling continues on a fixed loop without explicit abort signaling, which can produce stale UI updates or overlapping progress loops on navigation/retry edge paths.

Current guardrails:

- Client-side `revalidationInProgress` lock prevents duplicate submit starts.
- Actions are disabled while re-validation is active.
- Backend progress endpoint enforces no-cache semantics and canonical completion payloads.

### High - Results action disable behavior depends on CSS pointer blocking for links

Affected:

- [app/static/js/results.js](app/static/js/results.js)
- [app/static/css/results.css](app/static/css/results.css)
- [app/templates/results.html](app/templates/results.html)

Risk:

- Link actions are disabled primarily through `aria-disabled` + `pointer-events: none`; this is UI-strong but not a centralized action guard, increasing regression risk when styles or DOM structure change.

Current guardrails:

- Unified `setActionsDisabled` helper toggles link/button state.
- Disabled class and `aria-disabled` are applied consistently to `data-result-action` targets.

## Runtime Smoke Checklist (Phase 1.4)

1. Trigger re-validation in Standard mode and verify progress panel advances and redirects to the new results page.
2. Trigger re-validation in PRISM-only and BIDS-only modes and verify mode-specific completion messaging on return.
3. During active re-validation, verify Download/Cleanup/Validate Another/Re-validate actions are non-interactive until completion or failure.
4. Force a failed re-validation start (invalid/stale result context) and verify visible error feedback plus action re-enable.
5. Expand/collapse grouped error sections repeatedly and verify no loss of issue counts or chevron/expand-state coherence.

## Remediation Slices

### Slice A - Re-validation polling lifecycle hardening

Acceptance:

- Polling supports explicit cancellation/abort semantics.
- One active poll loop per re-validation run per tab.
- Retry paths cannot leave stale polling loops alive.

Validation:

- Focused results re-validation wiring assertions in [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py).
- Focused validation progress contract tests in [tests/test_web_validation_progress.py](tests/test_web_validation_progress.py).

### Slice B - Result-action state contract hardening

Acceptance:

- Result actions share one canonical disabled-state contract independent of styling details.
- Action state always re-enables after failure paths.
- Accessibility state (`aria-disabled`) remains consistent with interaction lock state.

Validation:

- Focused results workflow wiring assertions in [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py).
- Optional browser-level smoke checks for keyboard and pointer interaction lock behavior.

## Remediation Progress (2026-05-15)

- Slice A completed: re-validation polling now uses an explicit abortable polling-session contract (single active loop with signal-aware wait/fetch and pagehide cancellation).
- Slice A validation completed: [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py) and [tests/test_web_validation_progress.py](tests/test_web_validation_progress.py) are green.
- Slice B completed: result-action state is now guarded by explicit logic-level lock checks (click + keyboard) in addition to visual disabled styling.
- Slice B validation completed: [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py) is green.

## Exit Criteria for Results Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
