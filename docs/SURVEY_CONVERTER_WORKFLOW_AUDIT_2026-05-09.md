# Survey Converter Workflow Audit (2026-05-09)

## Scope
- Page: Converter -> Survey tab.
- Frontend files in scope:
  - `app/templates/converter_survey.html`
  - `app/static/js/converter-bootstrap.js`
  - `app/static/js/modules/converter/survey-convert.js`
  - `app/static/js/modules/converter/index.js`
  - `app/static/js/modules/converter/survey.js`
  - `app/static/js/modules/converter/limesurvey.js`
- Backend files in scope:
  - `app/src/web/blueprints/conversion_survey_blueprint.py`
  - `app/src/web/blueprints/conversion_survey_handlers.py`
  - `app/src/web/blueprints/conversion_survey_preview_handlers.py`
  - `app/src/web/blueprints/tools.py` (LimeSurvey template routes)

## Current Workflow Map (Observed)
1. Page loads `converter-bootstrap.js` from `converter.html`.
2. `converter-bootstrap.js` initializes survey module through `initSurveyConvert(...)`.
3. Survey workflow in `survey-convert.js` uses backend-first conversion APIs:
   - `POST /api/survey-prepare-workflow`
   - `POST /api/survey-convert-preview`
   - `POST /api/survey-convert-validate`
4. Survey template-generation flows use tools routes:
   - `POST /api/limesurvey-to-prism`
   - `GET /api/library-template/<template_key>`
   - `POST /api/limesurvey-save-to-project`

## Flagged Outdated Or Revisited Parts (Survey)

### A) Legacy module path remains beside active bootstrap path
- Active path: `converter-bootstrap.js` -> `survey-convert.js`.
- Additional path still exists: `modules/converter/index.js` imports `survey.js` and dynamically imports `converter-bootstrap.js`.
- Risk:
  - Two conceptual entrypoints for survey logic increase maintenance burden.
  - `survey.js` and `limesurvey.js` duplicate LimeSurvey quick-import logic with overlapping behavior.
- Flag: Revisited architecture. Should be consolidated to one entrypoint.

### B) Monolithic survey frontend module
- `survey-convert.js` now mixes:
  - workflow preparation,
  - preview review state,
  - conversion run control,
  - template-generation rendering,
  - participants schema handling.
- Risk:
  - hard to reason about state transitions,
  - high chance of stale UI state and hidden interaction regressions,
  - difficult to retire old subflows safely.
- Flag: Refactor required (extract by workflow phase).

### C) Frontend references to optional/removed controls
- Some handlers are guarded by null checks for controls not present in current template variants.
- Example classes of controls:
  - manual template-check button path (`checkProjectTemplatesBtn`)
  - optional survey structure/i18n warning containers
- Risk:
  - dead-adjacent branches remain unverified and can silently diverge.
- Flag: Candidate cleanup after route usage confirmation.

### D) Dual survey conversion endpoint styles
- `POST /api/survey-convert` returns ZIP-style output.
- `POST /api/survey-convert-validate` is the workflow endpoint used by current UI.
- Risk:
  - duplicate backend paths for similar conversion intent,
  - behavior drift and test overhead.
- Flag: Consolidate toward one primary workflow command contract.

### E) Route ownership split across conversion and tools blueprints
- Survey conversion routes are in dedicated conversion survey blueprint.
- Survey template generation routes live in tools blueprint.
- Risk:
  - cross-blueprint ownership makes survey workflow boundaries less obvious.
- Flag: Revisit API ownership boundaries after endpoint consolidation.

## Backend-First Refactor Roadmap

### Phase 1 (started): Remove frontend command orchestration where possible
- Move participants schema merge orchestration from frontend to backend endpoint contract.
- Status: Started and implemented on 2026-05-09.

### Phase 2: Consolidate survey entrypoints and retire duplicate module path
- Keep one converter survey entrypoint.
- Decommission or archive legacy `modules/converter/index.js` -> `survey.js` path for survey page behavior.

### Phase 3: Split survey-convert.js into workflow modules
- Candidate modules:
  - `survey-workflow-prepare.js`
  - `survey-workflow-preview.js`
  - `survey-workflow-convert.js`
  - `survey-participants-metadata.js`
  - shared state/store module
- Goal: explicit state transitions and smaller testable surfaces.

### Phase 3 Checkpoint (Implemented)
- Extracted participant-metadata workflow into
  `app/static/js/modules/converter/survey-participants-metadata.js`.
- `survey-convert.js` now delegates participant metadata rendering/saving flow
  to `createSurveyParticipantsMetadataController`.
- Extracted setup preparation orchestration into
  `app/static/js/modules/converter/survey-workflow-prepare.js`.
- `survey-convert.js` now delegates setup preparation, late setup blocker
  handling, and preparation finalization to
  `createSurveyWorkflowPrepareController`.
- Added wiring assertions in `tests/test_converter_workflow_wiring.py` to guard
  module import/usage and backend merge payload contract continuity.

### Phase 3 Checkpoint (2026-05-10 update)
- Extracted preview orchestration into
  `app/static/js/modules/converter/survey-workflow-preview.js`.
- `survey-convert.js` now delegates Preview button handling to
  `createSurveyWorkflowPreviewController` while keeping behavior unchanged.
- Updated `tests/test_converter_workflow_wiring.py` to assert preview module
  import/instantiation/delegation and preview endpoint ownership.

## Workflow Assessment Addendum (2026-05-10)

### 1) Dead-adjacent DOM branches still in active survey controller
- `survey-convert.js` still references controls that are not present in the
  active survey template (`converter_survey.html`), including:
  - `checkProjectTemplatesBtn`
  - `surveyI18nWarning` / `surveyI18nMessage`
  - `surveyStructureWarning` / `surveyStructureMessage`
  - `convertLibraryPathInput` / `convertBrowseLibraryBtn`
- Current behavior is guarded by null checks, so this does not crash, but it
  keeps stale branches in the main workflow path and increases maintenance cost.

### 2) Remaining monolith is now concentrated in convert-run path
- `prepare` and `preview` orchestration are extracted, but convert-run
  orchestration in `survey-convert.js` remains long/stateful.
- The convert path still contains request assembly, progress control, API
  handling, summary rendering, and error/retry transitions in one block.
- This is currently the biggest readability and regression-risk hotspot.

### 3) Legacy ZIP convert route is mounted but not used by current UI
- Backend still exposes both:
  - `POST /api/survey-convert` (ZIP style)
  - `POST /api/survey-convert-validate` (workflow JSON)
- Current frontend survey workflow uses `survey-convert-validate` and does not
  call `/api/survey-convert`.
- Keeping both routes is valid for compatibility, but should be explicitly
  documented as compatibility mode to avoid drift.

### 4) Project-switch stale-state risk remains
- On `prism-project-changed`, survey tab currently refreshes sourcedata quick
  select, but does not fully reset survey preview/conversion state.
- Risk: old preview-selection context and uploaded/server-picked source state
  can linger across project changes unless user manually clears inputs.

## Recommended Next Refactor Order
1. Extract convert-run orchestration into
   `app/static/js/modules/converter/survey-workflow-convert.js` using the same
   dependency-injected controller pattern as prepare/preview.
2. Move shared request composition/progress helpers into a small shared survey
   workflow module (or keep in `survey-convert.js` but isolate pure helpers).
3. Add explicit project-switch reset policy for survey tab state
   (clear selected source, clear preview selection state, rerun required).
4. Mark `/api/survey-convert` as compatibility path and ensure tests cover only
   intended consumers.
5. Remove stale DOM branches once template-check and i18n/structure warning
   controls are either restored in UI or explicitly retired.

### Phase 4: Endpoint consolidation
- Keep one primary conversion command endpoint for UI workflow.
- Keep legacy endpoint only as compatibility wrapper (or remove after migration).

### Phase 5: API ownership cleanup
- Evaluate whether template-generation routes should stay under tools blueprint or move under a survey workflow service boundary.
- Ensure frontend remains thin adapter and backend owns command decisions.

## Started Changes In This Iteration
- Backend merge helper added in canonical backend layer:
  - `src/participants_backend.py`
- Web handler now supports survey-selected merge mode:
  - `app/src/web/blueprints/projects_participants_handlers.py`
- Survey frontend save now calls backend merge mode instead of local merge orchestration:
  - `app/static/js/modules/converter/survey-convert.js`
- Regression tests added:
  - `tests/test_projects_participants_handlers.py`

## Phase-2 EntryPoint Consolidation (Implemented)
- Removed legacy quick-import initialization from converter module aggregator:
  - `app/static/js/modules/converter/index.js`
- Added duplicate-import guards to prevent repeated converter bootstrap
  initialization:
  - `app/static/js/converter-bootstrap.js`
  - `app/static/js/modules/converter/index.js`
- Added wiring-level assertions for this behavior:
  - `tests/test_converter_workflow_wiring.py`

## Lessons Learned
- The largest complexity source is not missing functionality but accumulated workflow responsibilities in one frontend file.
- Backend merge commands reduce stale-state bugs by making persistence behavior deterministic and centrally tested.
- Survey workflow improvements should continue as incremental extraction and delegation, not a full rewrite.
