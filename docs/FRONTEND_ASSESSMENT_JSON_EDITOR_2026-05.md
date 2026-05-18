# Frontend Structural Assessment - JSON Editor (Phase 3.1)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- JSON Editor page shell, file open flow, and project-autoload entry path
- Schema/file API reads through shared fallback helper
- Session-synced project root binding in JSON editor blueprint
- Save/download behavior and non-destructive source-file workflow

Key files:

- [app/templates/json_editor.html](app/templates/json_editor.html)
- [app/static/js/json-editor.js](app/static/js/json-editor.js)
- [app/src/json_editor_blueprint.py](app/src/json_editor_blueprint.py)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Open JSON Editor page -> `/editor/`
- Load schema for selected file type -> `/editor/api/schema/<json_type>`
- Load project JSON file by type -> `/editor/api/file/<json_type>` (GET)
- Save edited project JSON file -> `/editor/api/file/<json_type>` (POST)
- Validate JSON payload -> `/editor/api/validate`
- Editor availability/status check -> `/editor/api/status`

Assessment note:

- Frontend owns local-file parse/render/download UX.
- Backend blueprint owns project-root synchronization and editor API behavior for project-backed files.

## Current Stability Findings

### High - Mixed local-file editing and project-backed loading can blur persistence expectations

Affected:

- [app/static/js/json-editor.js](app/static/js/json-editor.js)
- [app/templates/json_editor.html](app/templates/json_editor.html)

Risk:

- UI supports both local file open and project API autoload. Users may assume Save/Download writes back to source automatically when local mode is active.

Current guardrails:

- Help panel explicitly frames Save as download/export behavior.
- Frontend download path is explicit and does not silently overwrite source files.

### High - Session project sync depends on per-request root resolution

Affected:

- [app/src/json_editor_blueprint.py](app/src/json_editor_blueprint.py)

Risk:

- If session project path becomes stale, the editor must not continue operating on the previous project root.

Current guardrails:

- `before_request` sync resolves current session project each request.
- On stale paths, editor falls back to empty/default root and load requests fail safely.

## Runtime Smoke Checklist (Phase 3.1)

1. Open JSON Editor directly and load a local `.json` file; edit and download to verify non-destructive export behavior.
2. Open JSON Editor with autoload query (`?autoload=<type>&from=project`) and verify project file loads via `/editor/api/file/<type>`.
3. Verify schema-backed form rendering for known file types and generic editor fallback for unknown types.
4. Simulate stale project session path and verify load/save API requests fail safely without using previously selected project root.
5. Verify API fallback helper is used for editor API calls when `/api` path remapping is required in packaged environments.

## Remediation Slices

### Slice A - Persistence semantics clarity

Acceptance:

- UI text clearly distinguishes local-file download flow from project-backed save flow.
- No silent source-file overwrites in local mode.

Validation:

- Keep wiring checks in [tests/test_json_editor_workflow_wiring.py](tests/test_json_editor_workflow_wiring.py).

### Slice B - Project root sync safety

Acceptance:

- Editor never reads/writes against stale prior project roots after session path changes.
- Stale path state fails safely and predictably.

Validation:

- Keep session sync regression coverage in [tests/test_json_editor_project_sync.py](tests/test_json_editor_project_sync.py).

## Exit Criteria for JSON Editor Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
