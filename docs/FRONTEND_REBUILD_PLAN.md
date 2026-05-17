# Frontend Rebuild Plan

## Goal

Rebuild the web frontend incrementally without changing the current visual design, while:

- reducing shell/template duplication
- splitting oversized page scripts into smaller page controllers
- keeping business logic in `src/` and Flask handlers thin
- preserving the current desktop/web runtime behavior

This is a structural refactor, not a redesign.

## Current State

The frontend is already partly modular, but it has grown unevenly:

- server-rendered Flask/Jinja pages under `app/templates/`
- shared shell and theme in `app/templates/base.html` and `app/static/css/studio-theme.css`
- page-level ES modules under `app/static/js/modules/`
- backend-facing requests mostly routed through `app/static/js/shared/api.js`

The main pressure points are not the CSS theme but the page controllers and page composition:

- `app/static/js/modules/projects/core.js` is very large
- `app/static/js/modules/projects/metadata.js` is very large
- `app/static/js/modules/converter/participants.js` is very large
- `app/static/js/modules/converter/survey-convert.js` is very large
- the converter shell combines several workflow templates into one page

The project uses many templates, but template count alone is not the core problem. Some split templates are healthy because they match distinct workflows. The real issue is that page state, DOM orchestration, modal handling, validation feedback, and server interactions have accumulated in a few oversized scripts.

## Recommendation

Do not migrate to React right now.

Reasons:

- the backend seam is already good enough for incremental frontend refactoring
- the current app runs in a desktop-like environment with loopback/fallback transport behavior that already works
- a React migration would add a bundler, a second rendering model, packaging work, and a large re-test surface
- the current pain is mostly controller complexity, not rendering capability

React or a similar framework becomes worth reconsidering only if all of the following become true:

- the team wants a long-term component platform for frequent UI feature work
- several major pages need rich client-side state, live composition, or cross-page shared state
- the team is willing to adopt a Node-based build pipeline and maintain it in packaging and release flows

For the current goal, a controller-and-components refactor inside the existing Flask/Jinja architecture has a much better cost-benefit ratio.

## Operating Constraints

- heavy lifting stays in the backend on all pages by default
- the Projects page is the main exception where some frontend-heavy orchestration may remain temporarily practical
- refactors should keep touched areas aligned with the repo expectation of about 85% code coverage
- repeated UI behavior or markup should be promoted into shared repo-wide modules/macros when patterns recur, instead of being copied page by page

Examples to favor during the refactor:

- shared file picker behavior and markup
- shared help-panel and section-card patterns
- shared page-specific API helpers and transport wrappers

Shared picker constraint:

- a common file/path picker must honor the general-settings server-picker preference so remote runs and network-mounted folders do not regress
- server-picker routing belongs in the shared picker contract, not in one-off page patches
- cross-platform handling is Windows-first for this repo's main users, even when refactoring from macOS
- avoid POSIX-only assumptions in frontend path handling; prefer backend-owned path resolution and only parse paths in the frontend when unavoidable

## Global Refactor Checklist

These rules should be treated as always-on constraints for frontend refactor work on this branch.

- backend heavy lifting is the default on every page; frontend code should orchestrate state, transport, and rendering rather than duplicate business logic
- the Projects page is the only area where some frontend-heavy orchestration may temporarily remain practical
- power users should not be forced to see explanatory guidance all the time; help panels and similar guidance should respect beginner mode where appropriate
- repeated UI or behavior should become shared repo-wide modules/macros instead of being recopied into page-specific implementations
- common file/path pickers must honor the general-settings server-picker preference for remote runs and network-mounted folders
- cross-platform behavior is Windows-first; avoid POSIX-only path assumptions and prefer backend-owned path resolution
- touched slices should stay aligned with the repo expectation of about 85% code coverage through focused tests

Additional global constraints worth keeping explicit while we continue:

- current-project context should remain a first-class source of truth so pages do not drift into stale project state
- shared components should preserve keyboard access and existing workflow semantics, not only visual output
- PRISM extends BIDS and must remain compatible with downstream BIDS tools, so frontend wording and flow should not imply replacement of BIDS behavior

## Target Architecture

Keep this split:

- `src/`: canonical business logic
- `app/src/`: route parsing, serialization, wiring
- `app/templates/`: page shells and server-rendered structure
- `app/static/js/`: page controllers, view helpers, transport, UI state

Move the frontend toward this shape:

### Template Layer

- `base.html` stays the single global shell
- each page keeps one thin top-level template
- repeated page chrome moves into macros/includes
- repeated modal markup moves into shared includes where practical
- tabs and repeated card/form blocks become reusable Jinja macros or focused includes

### JavaScript Layer

Each major page gets one page entrypoint and several narrow controllers.

Suggested pattern:

- `page-controller.js`: bootstraps the page
- `state.js`: page-local state and selectors
- `api-client.js`: page-specific transport wrappers
- `renderers/*.js`: DOM rendering only
- `controllers/*.js`: dialogs, forms, workflow actions, polling, validation
- `adapters/*.js`: bridge legacy DOM or server payload shapes while refactor is in progress

Rules:

- one module should not own the whole page
- DOM queries should be centralized near bootstrapping or view code
- API calls should not be scattered through render logic
- modal lifecycle and tab lifecycle should live in dedicated controllers
- page init should be idempotent and safe to call once

## Refactor Principles

1. Preserve visuals first.
2. Preserve route and API contracts unless backend cleanup is clearly needed.
3. Keep heavy lifting in backend services and handlers; frontend controllers should orchestrate state, transport, and rendering.
4. Reduce duplication by extracting shared shells/components, not by merging unrelated workflows into giant files.
5. Promote repeated UI/helpers to shared repo-wide modules or macros as soon as a pattern is real.
6. Refactor one page family at a time.
7. After each slice, run focused tests and smoke checks toward the repo's coverage target.

## Workstreams

### 1. Shared Shell and Component Extraction

Objective: reduce duplication across top-level templates without changing appearance.

Candidate extractions:

- standardized page shell wrapper
- standardized page header variants
- shared help-panel patterns
- shared file-picker patterns
- shared modal partials for common confirm/loading/error states
- shared empty-state, badge-row, and section-header patterns

Expected outcome:

- fewer repeated HTML structures
- smaller top-level templates
- more consistent markup hooks for JS controllers

### 2. Landing Page Rebuild

Primary targets:

- `app/templates/home.html`
- `app/templates/base.html`
- any home-page-specific bootstrap code or shared shell hooks used by the landing page

Why first:

- it is the safest page to establish the new shell/component conventions
- it has relatively low workflow risk compared with Projects or Converter
- it lets us extract reusable page-shell, hero, card-grid, and help-panel patterns before touching heavy stateful flows

Target split:

- keep the landing page controller minimal or controller-free if behavior stays simple
- extract shared shell macros/components used by the landing page and later pages
- standardize DOM hooks and page bootstrapping conventions from this page outward

Template goal:

- keep one thin `home.html` shell
- move repeated shell/card/help patterns into macros or includes where they can be reused by Projects and other pages
- avoid introducing page-specific one-off structures that cannot be reused later

### 3. Projects Page Rebuild

Primary targets:

- `app/templates/projects.html`
- `app/templates/includes/projects/*`
- `app/static/js/modules/projects/core.js`
- `app/static/js/modules/projects/metadata.js`

Why second:

- it is central to the product
- it already has some include structure to build on
- it contains large stateful workflows and repeated UI patterns

Target split:

- `page-controller.js`
- `project-selection-controller.js`
- `project-lifecycle-controller.js`
- `study-metadata-controller.js`
- `export-controller.js`
- `validation-controller.js`
- `projects-state.js`
- `projects-api-client.js`
- `projects-renderers.js`

Template goal:

- keep one `projects.html` shell
- preserve the existing project includes only where they represent real sections
- extract repeated section framing and form-row structures into macros
- avoid moving everything into one giant include tree

### 4. Converter Page Rebuild

Primary targets:

- `app/templates/converter.html`
- `app/templates/converter_*.html`
- `app/static/js/converter-bootstrap.js`
- `app/static/js/modules/converter/*`

Why third:

- it is a major workflow surface
- current behavior is already modular by modality, which is a good seam
- some workflow modules are still very large and need controller extraction

Target split by modality/workflow:

- shared converter shell controller
- participants controller set
- survey workflow controllers
- physio controller set
- biometrics controller set
- eyetracking controller set
- environment controller set

Cross-cutting shared controllers:

- job/polling controller
- tab activation controller
- file/source picker controller
- feedback/log renderer
- validation results renderer

Template goal:

- keep the converter as one top-level shell if that still matches the UX
- keep modality subtemplates only if they map to real workflow slices
- extract repeated panel, toolbar, and status markup into macros/includes

### 5. Template Editor and Survey Tools

Primary targets:

- `app/templates/template_editor.html`
- `app/static/js/template-editor.js`
- survey generator/customizer pages as a follow-on

Why fourth:

- the page is powerful but controller-heavy
- it would benefit from explicit editor, preview, items-panel, import, and save controllers

Target split:

- page controller
- source/load controller
- editor state controller
- preview controller
- item list controller
- validation/save controller
- language/variant controller

## Template Reduction Strategy

Reduce templates selectively, not aggressively.

Good reductions:

- duplicate page shell fragments into macros
- duplicate help panels into shared macros
- duplicate modal bodies/footers into partials
- duplicate section wrappers into reusable includes

Bad reductions:

- merging distinct workflows into giant templates just to lower file count
- removing includes that currently provide useful separation by page section or modality

Success should be measured by:

- smaller top-level templates
- clearer ownership per page section
- fewer repeated markup patterns
- easier JS bootstrapping and testing

not by reaching the lowest possible number of template files.

## Proposed Sequence

### Phase 0. Baseline and Safety Net

- inventory top-level pages, includes, and JS entrypoints
- add or improve focused smoke tests for Home and Projects bootstrapping
- document current page init paths and API dependencies

### Phase 1. Shared UI Foundation

- extract common shell macros/components
- standardize markup hooks and data attributes
- standardize page bootstrapping convention

### Phase 2. Landing Page Refactor

- thin `home.html` into a clean page shell
- extract reusable shell and section components from the landing page
- keep behavior and visuals unchanged

### Phase 3. Projects Refactor

- split `core.js` and `metadata.js` into page controllers and renderers
- simplify `projects.html` and section includes
- preserve current routes and behavior

Current branch progress on this phase:

- shared Projects template primitives are in place for path pickers and flow strips
- shared folder-picker behavior now lives in a repo-wide module that honors the server-picker preference and fallback browser flow
- extracted Projects controllers now cover file browsing, path-picking, init-on-BIDS, open/load handoff to the full Validator, page bootstrap/section wiring, project-selection guards/card switching, create preflight/conflict handoff, recent-project storage/rendering, project hints/beginner-help, settings/library state, current-project bootstrap/state visibility, maintenance/fix actions, metadata submit/button orchestration, metadata/citation sync status state, metadata description/schema/live-validation/save orchestration, metadata ORCID lookup/search orchestration, metadata load/readiness orchestration, metadata save/README coordination, metadata methods preview/generation orchestration, and create submission orchestration
- focused wiring tests cover these extracted seams so `core.js` can keep shrinking without losing route or workflow semantics
- the main remaining large frontend slice on this page is metadata payload assembly plus the remaining author/detail form wiring, rather than page-init, settings, current-project state, metadata-status state, metadata description/schema/live-validation orchestration, metadata ORCID lookup/search orchestration, metadata load/readiness orchestration, metadata save/README coordination, metadata methods preview/generation orchestration, submit-button orchestration, or hint controllers

Projects-phase stopping rule:

- stop extracting once `core.js` and `metadata.js` no longer each own multiple unrelated async workflows
- stop extracting once the remaining code in `metadata.js` is mostly local form wiring, payload assembly, and tightly coupled DOM helpers that are easier to read together than spread across more files
- only approve another extraction if the slice has its own request lifecycle, stale-request guard, save/load flow, or page-level state boundary that can be tested independently
- do not create a new controller only to move small helpers, one-off renderers, or a single form subsection without its own workflow semantics
- for the current Projects page, one more extraction is justified only if it cleanly removes a distinct workflow from `metadata.js`; otherwise treat the page as structurally complete and move on

### Phase 4. Converter Refactor

- split the largest modality scripts
- unify shared workflow plumbing
- reduce duplicate modal and status markup across converter sections

Current branch progress on this phase:

- extracted participants sourcedata quick-select workflow into `participants-sourcedata-quick-select.js`
- `participants.js` now delegates sourcedata list refresh, empty-selection clear/reset behavior, and project-change refresh to that controller seam
- extracted participants merge-conflict CSV download workflow into `participants-merge-conflict-download.js`
- `participants.js` now delegates merge-conflict export eligibility checks, error handling, and download response filename handling to that controller seam
- extracted participants merge decision payload serialization into `participants-merge-decision-payload.js`
- `participants.js` now delegates harmonization/session decision normalization and request payload append helpers to that module seam
- extracted participants merge preview refresh/status scheduling into `participants-merge-preview-refresh.js`
- `participants.js` now delegates refresh pending-state checks and debounced preview re-run scheduling for merge harmonization updates to that controller seam
- extracted participants merge summary render orchestration into `participants-merge-summary.js`
- `participants.js` now delegates merge summary/conflict/session-resolution/harmonization UI rendering to that controller seam while keeping request orchestration local
- extracted participants merge summary pure row render helpers into `participants-merge-summary-renderers.js`
- `participants-merge-summary.js` now delegates conflict-list and harmonization-row HTML generation to pure renderer helpers while keeping orchestration/event binding local
- extracted participants merge summary session-resolution row renderer into `participants-merge-summary-renderers.js`
- `participants-merge-summary.js` now delegates session-resolution row HTML generation to pure renderer helpers while preserving existing decision-state and listener orchestration
- extracted participants merge summary session hint/preview text formatting into pure renderer helpers
- `participants-merge-summary.js` now delegates session-resolution hint text construction to `participants-merge-summary-renderers.js`, keeping controller flow/event wiring unchanged
- extracted participants merge summary decision-initialization helpers into `participants-merge-summary-decisions.js`
- `participants-merge-summary.js` now delegates session-resolution and harmonization decision seed-map construction to that helper module while retaining state application and event wiring locally
- extracted participants merge summary harmonization status/convert-hint text resolvers into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates harmonization status text/class selection and convert-hint text selection to pure status helpers while keeping DOM updates and listeners in the controller
- extracted participants merge summary harmonization field hint/feedback resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates per-field keep-both hint/feedback text resolution to a pure helper while keeping DOM class toggles and input listeners in the controller
- extracted participants merge summary convert-button visual-state resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates convert-button enabled/tone view selection to a pure helper and applies it through one local updater to avoid duplicate UI toggling code
- extracted participants merge summary harmonization event payload resolver into `participants-merge-summary-decisions.js`
- `participants-merge-summary.js` now delegates action/new-column payload shaping for harmonization change/input handlers to that decision helper while preserving existing event timing and DOM flow
- extracted participants merge summary session-resolution event payload resolver into `participants-merge-summary-decisions.js`
- `participants-merge-summary.js` now delegates action/session/session-column payload shaping for session-resolution change handlers to that decision helper while preserving existing event timing and DOM flow
- extracted participants merge summary session-select enabled-state resolver into `participants-merge-summary-renderers.js`
- `participants-merge-summary.js` now delegates session select enabled/disabled view decisions to a shared helper used by both session row rendering and session-resolution change handlers
- extracted participants merge summary conflict-actions visibility/download-state resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates conflict-actions visibility and download button enablement decisions to a pure status helper while keeping DOM updates local
- extracted participants merge summary new-columns text/visibility resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates new-columns summary text/visibility view selection to a pure status helper while keeping DOM updates local
- extracted participants merge summary conflict-list html/visibility resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates conflict-list html/visibility selection to a pure status helper while keeping DOM updates local
- extracted participants merge summary alert/title/body text resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates merge summary alert tone, title text, and summary text decisioning to a pure status helper while keeping DOM updates local
- extracted participants merge summary badge-text resolver into `participants-merge-summary-status.js`
- `participants-merge-summary.js` now delegates matched/new/fill/conflict badge text construction to a pure status helper while keeping DOM updates local
- extracted participants merge summary local DOM visibility/content updaters inside `participants-merge-summary.js`
- `participants-merge-summary.js` now applies new-columns/conflict-list/conflict-actions views through shared local updaters to keep DOM mutations centralized and reduce repeated class toggles
- focused converter wiring tests cover this seam and are green: `tests/test_converter_participants_workflow_wiring.py` and `tests/test_converter_workflow_wiring.py`
- extracted survey file-separator controller into `survey-file-separator-controller.js`
- `survey-convert.js` now delegates delimiter detection, selected-separator resolution, and separator-group visibility updates to that controller while keeping existing conversion flow/event wiring unchanged
- extracted survey workflow response controller into `survey-workflow-response-controller.js`
- `survey-convert.js` now delegates workflow JSON response parsing through that controller instead of local wrapper helpers, while `survey-workflow-response-utils.js` remains the canonical parsing/summarization implementation
- extracted survey selected-input controller into `survey-selected-input-controller.js`
- `survey-convert.js` now delegates uploaded-file/server-path input resolution, request form-data input append, and input fingerprint construction through that controller while preserving existing workflow orchestration
- extracted survey session-input controller into `survey-session-input-controller.js`
- `survey-convert.js` now delegates survey/biometrics session value reads and detected-session picker hydration through that controller while preserving existing event binding and project-session refresh flow
- extracted survey convert feedback adapter into `survey-convert-feedback-adapter.js`
- `survey-convert.js` now delegates project-save summary and participant-registry feedback forwarding through that adapter, removing local pass-through wrappers while preserving feedback fallback behavior before controller initialization
- extracted survey run progress adapter into `survey-run-progress-adapter.js`
- `survey-convert.js` now delegates progress view forwarding (`set/start/advance/pause/resume/finish/hide`) through that adapter while preserving existing run lifecycle orchestration and callback signatures
- extracted survey active-run state adapter into `survey-active-run-state.js`
- `survey-convert.js` now delegates active run tracking/cancel state (`set/clear/cancel/get mode/get abort controller/get canceled-by-user`) through that adapter while preserving preview/convert run cancellation behavior
- extracted survey near-item-match adapter into `survey-near-item-match-adapter.js`
- `survey-convert.js` now delegates near-item-match fallback forwarding (`collect/build-confirmation/prompt`) through that adapter while preserving existing review-controller behavior and fallback semantics
- extracted survey value-offset editor adapter into `survey-value-offset-editor-adapter.js`
- `survey-convert.js` now delegates value-offset editor forwarding (`apply`, status/signature helpers, editor render/focus/state helpers, and manual-offset accessors) through that adapter while preserving the existing value-offset controller behavior
- extracted survey conversion-results adapter into `survey-conversion-results-adapter.js`
- `survey-convert.js` now delegates conversion summary/log/unmatched/validation forwarding (`append/reset/display`) through that adapter while preserving controller initialization order and behavior
- extracted survey template render adapter into `survey-template-render-adapter.js`
- `survey-convert.js` now delegates template-results and participant-metadata display forwarding (`single/groups/questions/metadata-section`) through that adapter while preserving template generation behavior
- removed local survey version-context pass-through wrappers in `survey-convert.js`
- `survey-convert.js` now calls `survey-version-context-utils.js` exports directly for version/session/run key + timeline context normalization/comparison helpers, reducing orchestrator glue without behavior changes
- removed local `resetSurveyImportFormState` pass-through wrapper from `survey-convert.js`
- `survey-convert.js` now calls `surveyImportFormStateController.resetSurveyImportFormState` directly at existing project-change and clear-input callsites, preserving import-form reset behavior
- removed dead local helpers from `survey-convert.js` (`getConvertMode` and `handleTemplateGeneration`) to reduce orchestrator-only glue that was no longer wired
- removed single-use `pickServerSurveyFile` wrapper from `survey-convert.js`
- server file picking now calls `pickServerFile(...)` directly in the existing browse-button handler with the same dialog options/filters
- removed one-call `handleModeSwitch` helper and inlined the same mode-UI setup at init, reducing local wrapper surface without changing visible behavior
- trimmed unused `openConverterTab` / `showConvertInfoMessage` destructuring from `surveyConvertFeedbackAdapter` wiring in `survey-convert.js`
- reduced `survey-convert-feedback-adapter.js` surface by removing unused `openConverterTab` and `showConvertInfoMessage` proxy methods (no remaining orchestrator callsites)
- reduced `survey-convert-feedback.js` public return surface to only the methods still consumed by adapter callers (`getProjectSaveSummary`, `getParticipantRegistryWarning`, `showParticipantRegistryWarning`)
- reduced `survey-near-item-match-adapter.js` surface to only `promptNearMatchSelection` and removed unused collect/build proxy methods + corresponding `survey-convert.js` destructuring
- removed duplicate initialization `updateConvertBtn()` call in `survey-convert.js` (single call retained)
- inlined single-use `openConverterTab` helper in `survey-convert-feedback.js` by calling `activateConverterTab(...)` directly inside the CTA click handler
- removed unused value-offset adapter destructuring entries from `survey-convert.js`; orchestrator now imports only methods it actually invokes
- reduced `survey-value-offset-editor-adapter.js` to export only the methods still used by `survey-convert.js`, removing unused proxy forwarders
- reduced `survey-value-offset-editor.js` controller return object to methods still consumed through current adapter/orchestrator wiring
- removed unused `getBiometricsSessionValue` destructuring from `survey-convert.js` (session input controller method remains owned in its module)
- removed unused `validationResultsCard`, `validationResultsHeader`, and `validationBadge` element destructuring from `survey-convert.js`
- removed unused local binding for template generation controller in `survey-convert.js` while keeping the initialization call
- removed single-use `pickServerParticipantsFile` wrapper from `participants.js` and inlined `pickServerFile(...)` at the browse-button callsite with the same options
- removed single-use `refreshParticipantsSourcedataQuickSelect` wrapper from `participants.js`; refresh now calls `participantsSourcedataQuickSelectController.refresh(resolveCurrentProjectPath())` directly
- removed single-use `getParticipantsSelectedFilename` wrapper from `participants.js`; file-name display now resolves directly via `resolveParticipantsFileName(...)` at callsite
- removed dead `openParticipantsEditor` helper (and now-unused `jsonEditorUrl` local) from `participants.js`

Converter-phase stopping rule (next-days completion target):

- stop participants merge-summary extraction once remaining code is primarily event binding glue and direct DOM node lookup/update with no additional reusable decision logic
- only approve another extraction when it yields a standalone, testable decision/payload/view function used in at least two call sites
- after one final participants seam, shift effort to the next largest converter surface (`survey-convert.js`) and avoid creating new participants helper modules unless fixing a bug
- treat Phase 4 participants work as structurally complete after three consecutive focused green runs with no stale wiring assertion drift

### Phase 5. Template Editor Refactor

- split the large controller into focused subcontrollers
- keep the same UI and save/load behavior

### Phase 6. Cleanup

- remove dead legacy scripts and one-off bootstraps
- standardize naming and entrypoints
- update developer documentation

## Effort Estimate

Approximate effort for one engineer working carefully alongside existing maintenance work:

- Phase 0 to 1: 3 to 5 days
- Landing page refactor: 2 to 4 days
- Projects refactor: 1 to 2 weeks
- Converter refactor: 2 to 3 weeks
- Template editor and adjacent tools: 1 to 2 weeks
- Cleanup and hardening: 3 to 5 days

Total: roughly 5 to 8 weeks for a serious structural rebuild without changing the current look.

This is materially cheaper and lower-risk than a React migration.

## Branch Strategy

Use a dedicated branch for the structural refactor.

Current working branch:

- `frontend-page-by-page-refactor`

Slice work into mergeable units:

- landing page shell/components
- shared shell/macros
- projects page controllers
- projects template cleanup
- converter shared controllers
- converter modality controllers
- template editor controllers
- cleanup/documentation

## Exit Criteria

The refactor is complete when:

- top-level templates are thinner and mostly declarative
- oversized page scripts are replaced by page controllers and focused helpers
- repeated markup patterns live in shared macros/includes
- current visuals and user workflows remain intact
- backend ownership remains in `src/` and route handlers stay thin
- targeted tests pass for touched workflows
