# Frontend Structural Assessment - Shared Modules (Phase 4.1)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest page-level frontend assessments and shared helper usage in workflow wiring suites.
- No finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.

Scope:

- Shared API fallback helpers used across page workflows
- Shared project-state snapshot/resolve helpers used for active-project continuity
- Shared job-status polling helper used by async converter workflows
- Cross-page contract consistency for fallback/retry/timeout behavior

Key files:

- [app/static/js/shared/api.js](app/static/js/shared/api.js)
- [app/static/js/shared/project-state.js](app/static/js/shared/project-state.js)
- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)

## Backend Command Ownership Map

Current ownership status: compliant for adapter utilities.

Shared module responsibility map:

- API fallback transport policy -> `fetchWithApiFallback` / `fetchWithRelativePathFallback` in [app/static/js/shared/api.js](app/static/js/shared/api.js)
- Active project state resolution -> snapshot/resolve/set helpers in [app/static/js/shared/project-state.js](app/static/js/shared/project-state.js)
- Async status polling contract -> `pollJobStatus` in [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)

Assessment note:

- These shared modules are infrastructure adapters and should not contain business-domain logic.
- Page modules consume these helpers to preserve consistent runtime semantics.

## Current Stability Findings

### High - Shared API fallback policy consistency is critical and globally coupled

Affected:

- [app/static/js/shared/api.js](app/static/js/shared/api.js)

Risk:

- Changes to fallback retry rules (relative path vs API path, credentials handling, protocol checks) can regress many pages simultaneously.

Current guardrails:

- Wiring suites assert key fallback exports and behavior strings.
- Multiple page-level suites verify import/use of shared fallback helpers.

### High - Project-state fallback chain can drift between store, helper, and globals

Affected:

- [app/static/js/shared/project-state.js](app/static/js/shared/project-state.js)

Risk:

- If store/global helper/global-var precedence changes unexpectedly, pages may observe inconsistent active project path/name/icon snapshots.

Current guardrails:

- Projects workflow tests assert event/state usage patterns that rely on shared snapshot semantics.
- Resolve helpers normalize string values to reduce whitespace/state noise.

### High - Polling helper timeout/retry policy controls async reliability across converters

Affected:

- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)

Risk:

- Relaxed retry limits or timeout handling can cause infinite polls or premature failures in long-running conversions.

Current guardrails:

- Converter workflow suite asserts bounded retry and timeout contract markers.
- Abort handling path supports deterministic cancellation behavior.

## Runtime Smoke Checklist (Phase 4.1)

1. Validate fallback helper behavior in file-based runtime and HTTP runtime contexts.
2. Verify project-state resolution remains consistent across store-driven and legacy global-driven pages.
3. Verify polling helper abort, timeout, and retry-limit semantics under simulated transient failures.
4. Verify representative pages continue importing shared helpers rather than introducing local fallback duplicates.

## Remediation Slices

### Slice A - Shared API fallback contract hardening

Acceptance:

- Fallback conditions and credentials behavior are explicitly documented and covered by focused assertions.
- Relative-path and API-path fallback behavior remain intentionally differentiated.

Validation:

- Keep focused shared API assertions in [tests/test_projects_workflow_wiring.py](tests/test_projects_workflow_wiring.py) and [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py).

### Slice B - Project-state and polling reliability contract hardening

Acceptance:

- Shared project-state precedence remains deterministic.
- Polling helper keeps bounded retry/timeout + abort semantics.

Validation:

- Keep focused projects/converter wiring assertions tied to shared module contracts.

## Remediation Progress (2026-05-15)

- Slice A completed: shared API fallback contract assertions now explicitly cover fallback origin selection, retry gating, credentials normalization, and one-time fetch-wrapper install behavior.
- Slice B completed: project-state fallback chain and job-polling abort/retry/timeout bounds are now protected by focused shared-module wiring assertions.
- Validation completed: [tests/test_shared_modules_contract_wiring.py](tests/test_shared_modules_contract_wiring.py) is green.

## Exit Criteria for Shared Modules Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
