# Frontend Structural Assessment - Projects (Phase 1.2)

Date: 2026-05-15

Scope:

- Projects page shell and project lifecycle UX actions
- Create, open, init-on-bids, and project switching flows
- Study metadata save/load readiness and preliminary/full save transitions
- Navbar current-project and recent-project interaction boundaries affecting project context

Key files:

- [app/templates/projects.html](app/templates/projects.html)
- [app/static/js/modules/projects/core.js](app/static/js/modules/projects/core.js)
- [app/static/js/modules/projects/project-selection.js](app/static/js/modules/projects/project-selection.js)
- [app/static/js/modules/projects/open-project.js](app/static/js/modules/projects/open-project.js)
- [app/static/js/modules/projects/metadata.js](app/static/js/modules/projects/metadata.js)
- [app/static/js/modules/projects/metadata-load.js](app/static/js/modules/projects/metadata-load.js)
- [app/static/js/modules/projects/metadata-save.js](app/static/js/modules/projects/metadata-save.js)
- [app/templates/base.html](app/templates/base.html)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Set/clear current project -> `/api/projects/current`
- Open/refresh project context -> `/api/projects/current` + project summary payload
- Initialize PRISM on existing BIDS -> `/api/projects/init-on-bids`
- Save project metadata -> `/api/projects/study-metadata`
- Save dataset description/citation sync -> `/api/projects/description`
- Metadata/citation health probes -> `/api/projects/metadata/status`, `/api/projects/citation/status`

Assessment note:

- Frontend currently orchestrates state transitions and readiness guards.
- Business logic remains backend-owned for write/validation operations.

## Current Stability Findings

### High - Project-switch and save readiness coupling is sensitive to async timing

Affected:

- [app/static/js/modules/projects/metadata.js](app/static/js/modules/projects/metadata.js)
- [app/static/js/modules/projects/metadata-load.js](app/static/js/modules/projects/metadata-load.js)
- [app/static/js/modules/projects/open-project.js](app/static/js/modules/projects/open-project.js)

Risk:

- If readiness state lags behind project-context change, save actions can appear non-responsive or run against stale context.

Current guardrails:

- Metadata-ready project-path tracking in load controller.
- Save-path retry behavior when metadata is not ready.
- Submit lock and per-flow in-flight protection.

### High - Context switching is distributed across page bootstrap and navbar handlers

Affected:

- [app/static/js/modules/projects/page-bootstrap.js](app/static/js/modules/projects/page-bootstrap.js)
- [app/templates/base.html](app/templates/base.html)
- [app/static/js/modules/projects/project-selection.js](app/static/js/modules/projects/project-selection.js)

Risk:

- Divergent guard behavior can reintroduce first-click loss or stale path edge cases.

Current guardrails:

- Unsaved/busy context-change confirmation in project-selection controller.
- Navbar recent-project pointerdown/click dedup and timeout handling.

## Runtime Smoke Checklist (Phase 1.2)

1. Open an existing project from Projects page and verify load state + save actions become available.
2. Switch projects via navbar recent-project list and verify current-project badge/path updates exactly once.
3. Trigger preliminary save with incomplete required fields and confirm expected warning/save behavior.
4. Trigger standard save after completing required fields and confirm status transitions to success.
5. Switch to New Project while unsaved draft exists and verify confirmation guard blocks accidental discard.

## Remediation Slices

### Slice A - Context-state unification guardrails

Acceptance:

- One canonical decision path for busy/unsaved guards before context-changing actions.
- No duplicate context-change side effects from mixed UI entry points.

Validation:

- Focused projects workflow wiring tests + navbar event wiring tests.

### Slice B - Metadata readiness and save resilience

Acceptance:

- Save actions clearly communicate loading-retry states.
- No save operation proceeds on stale project-path context.

Validation:

- Focused metadata load/save readiness wiring tests and targeted runtime smoke checks.

## Exit Criteria for Projects Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
