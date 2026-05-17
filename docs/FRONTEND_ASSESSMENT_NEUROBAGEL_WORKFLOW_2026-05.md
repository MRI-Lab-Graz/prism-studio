# Frontend Structural Assessment - Neurobagel Workflow (Phase 3.2)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- Participants tab Neurobagel annotation container and widget loader wiring
- Neurobagel dictionary fetch path and participants TSV column hydration path
- Widget annotate/remove behavior and integration with participants preview state
- Backend augmentation/local-participants APIs used by participants workflow

Key files:

- [app/templates/converter_participants.html](app/templates/converter_participants.html)
- [app/static/js/modules/converter/participants.js](app/static/js/modules/converter/participants.js)
- [app/static/neurobagel_widget.html](app/static/neurobagel_widget.html)
- [app/static/js/neurobagel.js](app/static/js/neurobagel.js)
- [app/src/web/blueprints/neurobagel.py](app/src/web/blueprints/neurobagel.py)

## Backend Command Ownership Map

Current ownership status: partially compliant; one widget fetch path bypasses shared API fallback helper.

Primary action -> backend command/endpoint mapping:

- Fetch Neurobagel participant dictionary -> `/api/neurobagel/participants`
- Load local project participant value options -> `/api/neurobagel/local-participants?project_path=<path>`
- Save uploaded-session participants JSON draft (legacy/upload mode) -> `/api/neurobagel/save-json`

Assessment note:

- Participants workflow frontend owns widget state and annotation UX orchestration.
- Backend owns dictionary augmentation and participants TSV value extraction.

## Current Stability Findings

### High - Duplicate participant-dictionary fetch implementations can diverge

Affected:

- [app/static/js/neurobagel.js](app/static/js/neurobagel.js)
- [app/static/neurobagel_widget.html](app/static/neurobagel_widget.html)

Risk:

- `neurobagel.js` uses shared API fallback for `/api/neurobagel/participants`, while widget-inline script defines its own `window.fetchNeurobagelParticipants` using direct `fetch`.
- In packaged/deployed environments, direct fetch path can drift from global API fallback behavior.

Current guardrails:

- Existing wiring tests verify shared fallback usage in `neurobagel.js`.
- Widget fetch failure falls back to empty structure and avoids hard crash.

### High - Annotation source-state precedence is subtle under preview vs saved schema modes

Affected:

- [app/static/js/modules/converter/participants.js](app/static/js/modules/converter/participants.js)
- [app/static/neurobagel_widget.html](app/static/neurobagel_widget.html)

Risk:

- Workflow intentionally prefers active preview columns over on-disk project columns in certain states; regressions in precedence can resurrect removed columns or hide new ones.

Current guardrails:

- Participants module keeps explicit active-preview vs project-column branches.
- Widget wiring tests cover removed-column and state-key resolution behavior.

## Runtime Smoke Checklist (Phase 3.2)

1. Open participants workflow, run preview, and confirm Neurobagel widget loads current preview columns in AVAILABLE/UNANNOTATED buckets.
2. Save annotation draft from participants flow and verify schema updates feed back into preview/annotation state.
3. Remove additional variable columns and confirm removed columns do not reappear from stale saved schema during active preview.
4. Toggle project context and verify local participants endpoint refresh aligns with active project path.
5. Exercise `/api/neurobagel/participants` fetch in packaged mode and verify fallback path behavior is consistent.

## Remediation Slices

### Slice A - Unified API fetch ownership for Neurobagel dictionary

Acceptance:

- Single canonical frontend fetch helper path for `/api/neurobagel/participants`.
- No direct, duplicate dictionary fetch implementation in widget-inline script.

Validation:

- Extend wiring checks in [tests/test_participants_neurobagel_widget_wiring.py](tests/test_participants_neurobagel_widget_wiring.py).

### Slice B - Preview vs saved-schema precedence hardening

Acceptance:

- Active preview columns remain source-of-truth during preview sessions.
- Removed/unmapped columns are not resurrected by stale saved schema data.

Validation:

- Keep and extend widget/state regression checks in [tests/test_participants_neurobagel_widget_wiring.py](tests/test_participants_neurobagel_widget_wiring.py).
- Keep augmentation behavior checks in [tests/test_web_neurobagel_augmentation.py](tests/test_web_neurobagel_augmentation.py).

## Exit Criteria for Neurobagel Workflow Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
