# Frontend Structural Assessment - Specifications (Phase 3.4)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- Specifications page shell and explanatory navigation model (Core vs Derivatives)
- Project-bound derivative link state behavior on initial render and project-change events
- Endpoint-availability gating for optional tool blueprints in mixed builds
- Backend route ownership and lightweight render adapter behavior

Key files:

- [app/templates/specifications.html](app/templates/specifications.html)
- [app/static/js/specifications.js](app/static/js/specifications.js)
- [app/prism-studio.py](app/prism-studio.py)

## Backend Command Ownership Map

Current ownership status: compliant for render-only page semantics.

Primary action -> backend command/endpoint mapping:

- Open Specifications page -> `/specifications`
- Derivative shortcut target (when available and project-bound) -> `/survey-generator` and `/recipes`

Assessment note:

- Page itself is documentation/navigation and does not execute business logic.
- Frontend script owns project-state-driven enabling/disabling of derivative shortcut links.

## Current Stability Findings

### High - Derivative link gating is frontend-state dependent and sensitive to stale project event state

Affected:

- [app/templates/specifications.html](app/templates/specifications.html)
- [app/static/js/specifications.js](app/static/js/specifications.js)

Risk:

- Shortcut enable/disable behavior depends on `data-current-project-path` and `prism-project-changed` event payload path values.
- If event payload shape or root data binding drifts, links can appear enabled/disabled incorrectly.

Current guardrails:

- Explicit root dataset source (`data-current-project-path`) for initial state.
- Dedicated project-change listener and deterministic link sync function.
- Build-availability flags (`endpoint_exists`) prevent broken links when optional tools are absent.

### High - Specifications route remains in monolithic app module instead of dedicated blueprint

Affected:

- [app/prism-studio.py](app/prism-studio.py)

Risk:

- Keeping page routes in the top-level app module increases coupling and can slow incremental isolation/migration of page-specific behavior.

Current guardrails:

- Route behavior is currently minimal and render-only.
- Template uses explicit endpoint-availability checks to reduce runtime link errors.

## Runtime Smoke Checklist (Phase 3.4)

1. Open Specifications with no active project and verify Survey Export/Recipes links remain disabled with guidance title.
2. Load a project and confirm derivative links become enabled and point to expected targets.
3. Trigger project switch/clear events and verify link state updates immediately without page reload.
4. Start app build without optional tool blueprint routes and verify unavailable links render as disabled placeholders.
5. Confirm Specifications page renders successfully in packaged optional-blueprint scenarios.

## Remediation Slices

### Slice A - Harden project-state contract for derivative link gating

Acceptance:

- Link enablement remains correct across project load, change, and clear events.
- Missing or malformed project-change payloads fail to disabled-safe state.

Validation:

- Keep/extend focused assertions in [tests/test_specifications_workflow_wiring.py](tests/test_specifications_workflow_wiring.py).

### Slice B - Route ownership consolidation planning

Acceptance:

- Specifications render route is tracked for eventual migration into a dedicated web blueprint with unchanged behavior.
- No frontend/business logic migration required beyond route ownership.

Validation:

- Keep optional-blueprint render coverage tests green.

## Exit Criteria for Specifications Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
