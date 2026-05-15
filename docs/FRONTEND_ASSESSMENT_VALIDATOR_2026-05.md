# Frontend Structural Assessment - Validator (Phase 1.3)

Date: 2026-05-15

Scope:

- Validator page shell and validation-target selection UX
- Current-project vs alternative-folder validation start flows
- Validation progress polling, resume behavior, and error recovery
- Advanced options behavior (mode override, BIDS warnings, schema version, library override)

Key files:

- [app/templates/index.html](app/templates/index.html)
- [app/static/js/index.js](app/static/js/index.js)
- [app/static/js/shared/api.js](app/static/js/shared/api.js)
- [app/static/js/shared/project-state.js](app/static/js/shared/project-state.js)
- [app/src/web/blueprints/validation.py](app/src/web/blueprints/validation.py)
- [src/web/validation.py](src/web/validation.py)

## Backend Command Ownership Map

Current ownership status: mostly compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Start current-project validation -> `/validate_folder`
- Start server-folder validation -> `/validate_folder`
- Start browser-folder upload validation -> `/upload`
- Poll active validation job -> `/api/progress/<job_id>`
- Resolve default library path by project context -> `/api/validation/default-library-path`
- Open validation result payload -> `/results/<result_id>`
- Re-run validation on same dataset (results handoff) -> `/revalidate/<result_id>`

Assessment note:

- Frontend owns UX orchestration, local folder packaging, and progress rendering.
- Backend owns validation execution, progress truth, mode filtering, warning filtering, and result persistence.

## Current Stability Findings

### High - Progress polling lifecycle is not abortable through an explicit signal contract

Affected:

- [app/static/js/index.js](app/static/js/index.js)
- [app/src/web/blueprints/validation.py](app/src/web/blueprints/validation.py)

Risk:

- Polling continues on a fixed loop without a shared abort contract, so stale UI updates can occur after context shifts, reload edges, or overlapping retry attempts.

Current guardrails:

- `validationInProgress` client lock blocks duplicate submit starts.
- Stored-job compatibility checks prevent resume across mismatched targets.
- Backend progress payload resets stale completion metadata when launching a reused job id.

### High - Target-path resolution and submit-path assembly are distributed across multiple branches

Affected:

- [app/static/js/index.js](app/static/js/index.js)
- [app/templates/index.html](app/templates/index.html)

Risk:

- Multiple path sources (`project-state`, hidden inputs, dataset attributes, global window path) plus branch-specific form assembly can drift and cause wrong-target validation or inconsistent option payloads.

Current guardrails:

- Path normalization helper for accidental relative/URI variants.
- Global `prism-project-changed` listener refreshes target display and default library context.
- Explicit current-vs-folder target radio model with state-based button gating.

## Runtime Smoke Checklist (Phase 1.3)

1. Validate current project (default target) and verify progress panel updates then redirects to results.
2. Switch to alternative folder target (browser picker) and verify metadata-only upload flow starts and progress resumes correctly after reload.
3. Switch to server-folder target and verify folder path is used directly without browser upload payload.
4. Toggle advanced options on/off and verify disabled state resets mode/schema/default library behavior.
5. Start a validation run, reload page, and verify resume button only appears for compatible target context.

## Remediation Slices

### Slice A - Abortable progress lifecycle and reconnect resilience

Acceptance:

- Polling supports explicit cancellation/abort semantics.
- One active poll loop per active validation job per tab.
- Resume/reconnect never produces duplicate progress loops for the same job.

Validation:

- Focused validator workflow wiring tests.
- Focused web validation progress tests for stale metadata reset and progress endpoint contract.

### Slice B - Canonical target context and request assembly consolidation

Acceptance:

- One canonical target-context resolver is used before all validation starts.
- Shared request-assembly helpers produce identical mode/schema/library payload semantics across current-folder, server-folder, and upload flows.
- Library override is submitted only when explicitly different from the resolved default.

Validation:

- Focused validator workflow wiring tests for override and target-selection behavior.
- Focused upload/validate-folder endpoint contract tests.

## Remediation Progress (2026-05-15)

- Slice A completed: validator progress polling now uses an explicit abortable polling-session contract (single active loop with signal-aware wait/fetch and pagehide cancellation).
- Slice A validation completed: [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py) and [tests/test_web_validation_progress.py](tests/test_web_validation_progress.py) are green.
- Slice B completed: canonical target/request assembly now routes through shared resolver + append helpers across current-project, server-folder, and upload starts.
- Slice B validation completed: [tests/test_validator_workflow_wiring.py](tests/test_validator_workflow_wiring.py) and [tests/test_web_validation_progress.py](tests/test_web_validation_progress.py) are green.

## Exit Criteria for Validator Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
