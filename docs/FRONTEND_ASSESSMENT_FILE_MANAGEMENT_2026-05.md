# Frontend Structural Assessment - File Management (Phase 2.5)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- File Management page shell and multi-tool tab flows (Renamer, Organizer, Wide-to-Long, Delete)
- Server/local file selection modes and active-project gating for copy/apply actions
- Wide-to-Long preview/convert workflow and project save target behavior
- Subject/entity rewrite and delete preview-then-apply safety contracts

Key files:

- [app/templates/file_management.html](app/templates/file_management.html)
- [app/static/js/file_management.js](app/static/js/file_management.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)

## Backend Command Ownership Map

Current ownership status: mostly compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Open File Management page -> `/file-management`
- Wide-table raw peek (column/sample preview) -> `/api/file-management/raw-peek`
- Wide-to-Long preview transform -> `/api/file-management/wide-to-long-preview`
- Wide-to-Long convert + save -> `/api/file-management/wide-to-long`
- Batch organizer conversion/copy -> `/api/batch-convert`
- Physio renamer preview/copy/download -> `/api/physio-rename`
- Subject rewrite options/preview/apply -> `/api/file-management/subject-rewrite`
- Entity rewrite options/preview/apply -> `/api/file-management/entity-rewrite`
- File delete options/preview/apply -> `/api/file-management/delete`

Assessment note:

- Frontend owns tool-specific workflow orchestration and preview UX.
- Backend owns actual file rewrite/convert/delete execution and project-root safety enforcement.

## Current Stability Findings

### High - Multi-tool script centralization increases cross-tool state coupling risk

Affected:

- [app/static/js/file_management.js](app/static/js/file_management.js)

Risk:

- One large script manages several tool states and server/local picker branches; regressions in shared helper logic can affect unrelated tool tabs.

Current guardrails:

- Shared API fallback helper used consistently.
- Per-tool enable/disable guards tied to active project and selected inputs.
- Explicit reset/clear functions for server selection hints and path state.

### High - Preview-then-apply safety contract relies on frontend sequence integrity

Affected:

- [app/static/js/file_management.js](app/static/js/file_management.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)

Risk:

- Subject/entity/delete apply flows require a matching preview signature in session; frontend sequencing drift can cause confusing apply failures or stale operation intent.

Current guardrails:

- Backend preview signatures (`*_last_preview`) are enforced before apply.
- Frontend exposes explicit preview-first UX and blocks apply without preview.
- Backend validates active project root existence before destructive actions.

## Runtime Smoke Checklist (Phase 2.5)

1. Run Wide-to-Long raw peek and preview, then convert with an active project and verify save target under `sourcedata/wide_to_long/`.
2. Run organizer preview/copy using both local files and server-picked paths and verify project-path guards.
3. Run physio renamer preview then copy and verify flat-copy restrictions for PRISM root destination are enforced.
4. Execute subject rewrite preview/apply and entity rewrite preview/apply and verify apply is rejected when preview signature is stale.
5. Run file delete options/preview/apply flow and verify apply requires matching preview context.

## Remediation Slices

### Slice A - Cross-tool state isolation and guard consistency

Acceptance:

- Shared helper changes cannot break unrelated tool tab state.
- Server/local picker transitions always clear stale selection state.
- Project-gated actions remain disabled whenever active project is missing.

Validation:

- Focused wiring assertions in [tests/test_file_management_workflow_wiring.py](tests/test_file_management_workflow_wiring.py).
- Focused save-path guard assertions in [tests/test_file_management_save_paths.py](tests/test_file_management_save_paths.py).

### Slice B - Preview/apply safety contract hardening

Acceptance:

- Apply operations always require a valid, matching preview signature.
- User-facing errors are actionable when preview signature is stale.
- Destructive operations remain blocked on stale/missing project paths.

Validation:

- Existing rewrite/delete preview contract tests and add focused regression checks where gaps remain.
- Keep route-level guard checks in [tests/test_file_management_save_paths.py](tests/test_file_management_save_paths.py).

## Exit Criteria for File Management Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
