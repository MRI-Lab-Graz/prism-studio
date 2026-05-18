# Frontend Structural Assessment - Converter (Phase 1.1)

Date: 2026-05-12 (updated 2026-05-17)

Synchronization status (2026-05-17):

- Cross-checked against current converter modularization baseline and shared polling/run-state contracts.
- No finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.

Scope:

- Converter shell page and all converter tabs
- Survey, Participants, Biometrics, Physio, Eyetracking, Environment converter workflows
- Shared converter polling and project-state coupling

Key files:

- [app/templates/converter.html](app/templates/converter.html)
- [app/static/js/converter-bootstrap.js](app/static/js/converter-bootstrap.js)
- [app/static/js/modules/converter/](app/static/js/modules/converter/)
- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)
- [app/src/web/blueprints/conversion.py](app/src/web/blueprints/conversion.py)
- [app/src/web/blueprints/conversion_survey_handlers.py](app/src/web/blueprints/conversion_survey_handlers.py)
- [app/src/web/blueprints/conversion_participants_blueprint.py](app/src/web/blueprints/conversion_participants_blueprint.py)

## Backend Command Ownership Map

Current ownership status: mostly compliant.

Primary action -> backend command/endpoint mapping:

- Survey prepare/preview/convert -> /api/survey-workflow-command
- Survey detect version contexts -> /api/survey-detect-version-contexts
- Participants flow -> /api/participants-* endpoints
- Batch physio/eyetracking convert -> /api/batch-convert-start, /api/batch-convert-status/<job_id>, /api/batch-convert-cancel/<job_id>
- Environment convert -> /api/environment-convert-start, /api/environment-convert-status/<job_id>, /api/environment-convert-cancel/<job_id>
- Sourcedata quick select -> /api/projects/sourcedata-files, /api/projects/sourcedata-file

Ownership gap candidates to validate/fix:

- Any frontend-side transformation logic that changes domain behavior before backend execution must be moved into backend (or re-validated server-side).
- Polling/cancel/retry policy should remain frontend UX only; job state truth must remain backend-owned.

## Current Stability Findings

### High - Polling helper has no abort signal contract

Affected:

- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)

Risk:

- In-flight polling cannot be externally aborted through a shared signal contract, causing stale UI updates after tab/project changes.

Recommendation:

- Extend pollJobStatus with AbortSignal support and enforce cancel-on-project-change behavior in converter tabs.

Coverage:

- Add focused tests for cancellation semantics and stale callback suppression.

### High - Converter shell project-change reset is partial

Affected:

- [app/static/js/converter-bootstrap.js](app/static/js/converter-bootstrap.js)
- [app/static/js/modules/converter/participants.js](app/static/js/modules/converter/participants.js)
- [app/static/js/modules/converter/survey-convert.js](app/static/js/modules/converter/survey-convert.js)

Risk:

- project-changed listeners are distributed and page-level reset behavior is uneven across modalities.

Recommendation:

- Introduce one converter-wide reset contract invoked on project change and verify each tab opts in.

Coverage:

- Add or extend wiring tests to assert standardized reset hooks for every modality tab.

### Medium - Log rendering used innerHTML in modality modules

Affected:

- [app/static/js/modules/converter/eyetracking.js](app/static/js/modules/converter/eyetracking.js)
- [app/static/js/modules/converter/physio.js](app/static/js/modules/converter/physio.js)

Risk:

- even escaped content combined with innerHTML appends increases maintenance risk and can regress to XSS if future escaping changes.

Recommendation:

- Use createElement/textContent append strategy for logs.

Status (2026-05-12):

- Resolved for Eyetracking and Physio in Slice C via safe DOM append helpers.
- Locked with wiring assertions in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).

Coverage:

- Add regression test to verify log rendering path does not rely on raw innerHTML concatenation for server-provided text.

### Medium - Status polling timeout can rely too heavily on wall clock

Affected:

- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)

Risk:

- if system time changes significantly, timeout behavior can degrade.

Recommendation:

- Use monotonic elapsed tracking fallback (interval counter + monotonic timestamp where available).

Coverage:

- Add deterministic timer tests.

## Hostile Usage Findings

### High - Click-storm and duplicate submit guard consistency differs by tab

Affected:

- converter modality modules under [app/static/js/modules/converter/](app/static/js/modules/converter/)

Risk:

- repeated trigger sequences can create unnecessary parallel backend jobs if button locking is inconsistent.

Recommendation:

- standardize submit lock/cancel lock behavior across all modality tabs with shared helper.

Coverage:

- Add tab-by-tab duplicate-submit tests.

### Medium - Job ID replay exposure should be validated uniformly

Affected:

- backend status/cancel endpoints in [app/src/web/blueprints/conversion.py](app/src/web/blueprints/conversion.py)

Risk:

- if job ownership checks differ across handlers, stale/replayed job IDs may leak status data.

Recommendation:

- centralize ownership checks in job store accessor.

Coverage:

- Add negative tests for foreign/stale job IDs.

## Fast Execution Findings

### Medium - Repeated DOM rebuild pressure during long conversion sessions

Affected:

- converter log/progress areas in modality modules

Risk:

- high-frequency log appends and full container rewrites can add UI lag in long jobs.

Recommendation:

- batch DOM writes per tick, use DocumentFragment for burst appends.

Coverage:

- Add a lightweight perf smoke benchmark for log append throughput.

## Runtime Smoke Checklist (Phase 1.1)

1. Trigger converter runs in Participants, Survey, and one async modality (Environment/Physio/Eyetracking) and verify one active run per action path.
2. Switch project context during an active async conversion and verify polling stops cleanly with no stale status/log updates.
3. Verify repeated click attempts on preview/convert actions do not create duplicate backend jobs.
4. Verify status/cancel handling for unknown or stale job IDs returns safe failure feedback without leaking prior job state.
5. Run long log-producing conversions and confirm log rendering uses safe DOM append paths without UI lockups.

## Remediation Slices

### Slice A (highest risk): polling cancellation + project-change stability

Files:

- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)
- converter modality modules that poll status
- [app/static/js/modules/converter/polling-run-state.js](app/static/js/modules/converter/polling-run-state.js)

Implementation checkpoint (2026-05-12):

- Completed: added abort-signal support in shared poll helper.
- Completed: extracted shared converter polling lifecycle helper to reduce duplicated state logic in large modality scripts.
- Completed: wired Physio/Eyetracking/Environment to abort active polling on project changes to prevent stale UI updates.
- Completed: wired Physio/Eyetracking/Environment to request backend job cancellation on project changes when a job is active.

Acceptance:

- all converter polling loops honor abort signal
- no stale UI update after project switch/cancel

Validation:

- ./rtk test focused converter workflow and polling tests

### Slice B: command ownership and duplicate-submit hardening

Files:

- converter modality modules and shared helpers
- conversion backend status/cancel ownership checks

Acceptance:

- one tab action -> one backend command start
- repeat clicks do not create parallel jobs unless explicitly allowed

Validation:

- ./rtk test converter contract suites + negative replay tests

Implementation checkpoint (2026-05-12):

- Started: extracted shared run controller [app/static/js/modules/converter/job-run-controller.js](app/static/js/modules/converter/job-run-controller.js).
- Started: wired Environment/Physio/Eyetracking to prevent duplicate run starts and centralize per-run job tracking.
- Started: wired Biometrics preview/detect/convert actions to shared run lock to prevent cross-button click storms.
- Started: wired Participants preview/convert actions to shared run lock with guaranteed release across preflight early-return branches.
- Started: added participants preview/convert click-storm regression assertions in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).
- Started: added biometrics preview/detect/confirm click-storm regression assertions in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).
- Started: added environment/physio/eyetracking handler-block replay assertions (run lock + single active job lifecycle + release-path checks) in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).
- Started: added negative replay checks for unknown async job IDs (status/cancel -> 404) in [tests/test_web_blueprints_conversion.py](tests/test_web_blueprints_conversion.py).
- Started: extracted survey template-generation logic from [app/static/js/modules/converter/survey-convert.js](app/static/js/modules/converter/survey-convert.js) into [app/static/js/modules/converter/survey-template-generation.js](app/static/js/modules/converter/survey-template-generation.js).

### Slice C: performance and rendering safety polish

Files:

- modality log rendering paths

Acceptance:

- no raw innerHTML concatenation for server text logs
- reduced UI lag under high-volume status logs

Validation:

- ./rtk test targeted module tests + perf smoke

Implementation checkpoint (2026-05-12):

- Completed: replaced risky `innerHTML +=` log appends in [app/static/js/modules/converter/eyetracking.js](app/static/js/modules/converter/eyetracking.js) with safe DOM appends (`createElement`, `textContent`).
- Completed: replaced risky `innerHTML +=` log appends in [app/static/js/modules/converter/physio.js](app/static/js/modules/converter/physio.js) with safe DOM appends (`createElement`, `textContent`).
- Completed: added regression assertions in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py) to prevent reintroduction of raw log concatenation on `eyetrackingBatchLog`/`physioBatchLog`.

### Slice D: converter log throughput/perf smoke + rendering-path audit

Files:

- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)
- [app/static/js/modules/converter/environment.js](app/static/js/modules/converter/environment.js)
- [app/static/js/modules/converter/physio.js](app/static/js/modules/converter/physio.js)
- [app/static/js/modules/converter/eyetracking.js](app/static/js/modules/converter/eyetracking.js)
- [app/static/js/modules/converter/biometrics.js](app/static/js/modules/converter/biometrics.js)
- [app/static/js/modules/converter/survey-conversion-log.js](app/static/js/modules/converter/survey-conversion-log.js)
- [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py)

Acceptance:

- polling loops use bounded cadence/timeouts/retry caps
- streaming converter logs stay on DOM append/text paths (no `innerHTML +=` concatenation)

Validation:

- ./rtk test tests/test_converter_workflow_wiring.py -k "bounded_retry_timeout_contract or polling_cadence_perf_smoke or safe_append_paths" -q
- ./rtk test tests/test_converter_workflow_wiring.py -q

Implementation checkpoint (2026-05-12):

- Started: added polling-helper throughput/perf smoke assertions for bounded interval/timeout/retry behavior in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).
- Started: added tab-level polling cadence assertions for Environment/Physio/Eyetracking status polling contracts in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).
- Started: added rendering-path audit assertions for Environment/Biometrics/Survey log controller append behavior in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).
- Completed: added shared `appendLogBatch` helper in [app/static/js/converter-bootstrap.js](app/static/js/converter-bootstrap.js) using `DocumentFragment` to reduce per-line DOM churn during burst log updates.
- Completed: wired Environment on-status log bursts to `appendLogBatch` (with safe fallback) in [app/static/js/modules/converter/environment.js](app/static/js/modules/converter/environment.js).
- Completed: wired Biometrics API log-array handling to batched append via `appendBiometricsLogEntries` in [app/static/js/modules/converter/biometrics.js](app/static/js/modules/converter/biometrics.js).
- Completed: extended wiring assertions for `appendLogBatch` integration in [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py).

Implementation checkpoint (2026-05-17):

- Completed: reduced survey converter orchestrator glue in [app/static/js/modules/converter/survey-convert.js](app/static/js/modules/converter/survey-convert.js) by removing dead/single-use wrappers and unused bindings while preserving behavior.
- Completed: narrowed survey adapter/controller API surfaces to active callsites only:
	- [app/static/js/modules/converter/survey-convert-feedback-adapter.js](app/static/js/modules/converter/survey-convert-feedback-adapter.js)
	- [app/static/js/modules/converter/survey-convert-feedback.js](app/static/js/modules/converter/survey-convert-feedback.js)
	- [app/static/js/modules/converter/survey-near-item-match-adapter.js](app/static/js/modules/converter/survey-near-item-match-adapter.js)
	- [app/static/js/modules/converter/survey-value-offset-editor-adapter.js](app/static/js/modules/converter/survey-value-offset-editor-adapter.js)
	- [app/static/js/modules/converter/survey-value-offset-editor.js](app/static/js/modules/converter/survey-value-offset-editor.js)
- Completed: reduced participants module glue in [app/static/js/modules/converter/participants.js](app/static/js/modules/converter/participants.js) by inlining single-use server-picker/sourcedata-refresh helpers and removing dead local helpers.
- Completed: aligned and expanded wiring guards in:
	- [tests/test_converter_workflow_wiring.py](tests/test_converter_workflow_wiring.py)
	- [tests/test_converter_participants_workflow_wiring.py](tests/test_converter_participants_workflow_wiring.py)
- Validation (focused): `pytest -q tests/test_converter_workflow_wiring.py tests/test_converter_participants_workflow_wiring.py` -> 36 passed.
- Validation (syntax): `node --check` green for touched converter modules.

## Exit Criteria for Converter Assessment

- Critical findings: none open.
- High findings: tracked by remediation slices with owners and tests.
- Backend-command ownership map is complete and validated.
- Focused RTK suite green after each slice.
