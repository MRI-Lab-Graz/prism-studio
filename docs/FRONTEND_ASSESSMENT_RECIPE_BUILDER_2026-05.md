# Frontend Structural Assessment - Recipe Builder (Phase 2.2)

Date: 2026-05-15

Synchronization status (2026-05-17):

- Cross-checked against latest converter refactor baseline in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- No page-specific finding severity changes in this synchronization pass.
- Existing remediation slices and validation scope below remain authoritative.


Scope:

- Recipe Builder page shell and modality-aware template selection flow
- Item pool, inversion controls, variation management, and scale-canvas interactions
- Recipe load/save lifecycle with project-scoped persistence guarantees
- JSON preview and compatibility handling for advanced score structures

Key files:

- [app/templates/recipe_builder.html](app/templates/recipe_builder.html)
- [app/static/js/recipe_builder.js](app/static/js/recipe_builder.js)
- [app/src/web/blueprints/tools.py](app/src/web/blueprints/tools.py)
- [app/src/web/blueprints/tools_recipe_builder_handlers.py](app/src/web/blueprints/tools_recipe_builder_handlers.py)

## Backend Command Ownership Map

Current ownership status: compliant with adapter-layer intent.

Primary action -> backend command/endpoint mapping:

- Open Recipe Builder page -> `/recipe-builder`
- List available modality templates -> `/api/recipe-builder/surveys`
- Load item pool + template metadata -> `/api/recipe-builder/items`
- Load existing project recipe -> `/api/recipe-builder/load`
- Save recipe JSON to project recipes folder -> `/api/recipe-builder/save`

Assessment note:

- Frontend owns interactive scale composition UX (selection, drag/drop, inversion, variation state).
- Backend owns template/recipe discovery, recipe validation, task-existence gating, and canonical write paths.

## Current Stability Findings

### High - Multi-surface async race handling is token-based but spread across separate load flows

Affected:

- [app/static/js/recipe_builder.js](app/static/js/recipe_builder.js)

Risk:

- Survey-list and load-data requests use separate request tokens and task guards; regression in one branch can reintroduce stale state application during project/template/modality switches.

Current guardrails:

- `surveyListRequestToken` and `loadRequestToken` stale-response checks.
- `prism-project-changed` listener resets builder state and reloads template lists.
- Immediate stale-state clearing before async template load resolves.

### High - Save compatibility boundary between editable and locked scores is frontend-sensitive

Affected:

- [app/static/js/recipe_builder.js](app/static/js/recipe_builder.js)
- [app/src/web/blueprints/tools_recipe_builder_handlers.py](app/src/web/blueprints/tools_recipe_builder_handlers.py)

Risk:

- Frontend preserves advanced score structures by marking unsupported score forms as locked; if this compatibility contract drifts, save operations can unintentionally alter advanced recipe semantics.

Current guardrails:

- Locked-score detection tracks unsupported methods/fields and preserves original score payload segments.
- Backend `validate_recipe` enforces recipe schema/constraint checks before write.
- Backend requires task presence in project/official library before allowing save.

## Runtime Smoke Checklist (Phase 2.2)

1. Load a survey template and verify item pool, inversion controls, and scale canvas initialize without stale entries.
2. Switch modality between survey and biometrics and verify list/load state resets cleanly with no carry-over selection.
3. Build multi-scale recipe with variation-specific scores and verify exclusivity rules for item assignment per variation.
4. Save valid recipe and confirm output path is `code/recipes/{modality}/recipe-<task>.json`.
5. Load recipe containing advanced/unsupported score fields and verify locked-score warning appears and advanced content is preserved after save.

## Remediation Slices

### Slice A - Async state transition hardening across project/modality/template pivots

Acceptance:

- Stale async responses never mutate active UI state.
- Project-change resets always clear task-bound builder state before new loads apply.
- Template and modality pivots preserve deterministic empty/loading/error states.

Validation:

- Focused wiring assertions in [tests/test_recipe_builder_workflow_wiring.py](tests/test_recipe_builder_workflow_wiring.py).
- Targeted handler contract tests for list/items/load surfaces in [tests/test_recipe_builder_handlers.py](tests/test_recipe_builder_handlers.py).

### Slice B - Save-path and score-compatibility contract hardening

Acceptance:

- Save always targets project-local recipes path and never mutates legacy root recipe folders.
- Invalid recipes are rejected with explicit validation feedback.
- Locked advanced score payloads remain unchanged through load/save roundtrip.

Validation:

- Focused handler tests in [tests/test_recipe_builder_handlers.py](tests/test_recipe_builder_handlers.py).
- Add explicit roundtrip compatibility assertions for locked-score preservation behavior.

## Exit Criteria for Recipe Builder Assessment

- Critical findings: none open.
- High findings: either resolved or tracked with explicit remediation slices and tests.
- Runtime smoke checklist completed and documented.
