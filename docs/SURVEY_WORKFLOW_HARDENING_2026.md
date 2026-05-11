:orphan:

# Survey Workflow Hardening Archive (2026-05-11)

This file preserves the detailed implementation log that previously lived in ROADMAP.md under Priority 1.35.

## Priority 1.35 — Survey converter workflow audit and backend command consolidation 🚧 IN PROGRESS

Reduce survey converter complexity by auditing active workflow paths, flagging
outdated/revisited parts, and moving workflow commands from frontend orchestration
into backend contracts.

**Stacked PR plan (near-future merge to `main`):**
- Current integration status:
  - Branch `survey-workflow-hardening` is clean and synced with upstream.
  - Ahead of `origin/main` by 21 commits, behind by 0.
  - Latest full gate: `./rtk coverage` passing at 81.09%.
- Split strategy (scope-first, then sequential merge):
  - **PR 1 — Backend canonical service + adapter decoupling (lowest risk)**
    - Scope:
      - `src/survey_workflow_service.py` canonical ownership for survey workflow helpers/constants.
      - Thin wrapper adoption in survey web adapters (`conversion_survey_handlers.py`, `conversion_survey_preview_handlers.py`) for flag parsing and stale-response shaping.
      - No intended frontend UX behavior changes.
    - Validation gate:
      - `pytest tests/test_survey_workflow_service.py -q`
      - `pytest tests/test_web_blueprints_conversion.py -k "SurveyConvertPreviewEndpoint or SurveyConvertValidateEndpoint or handlers_stale_wrapper" -q`
      - `./rtk coverage`
  - **PR 2 — Backend workflow endpoint contract stabilization**
    - Scope:
      - Unified command dispatch hardening (`/api/survey-workflow-command`) and payload-shape parity across prepare/preview/convert.
      - Stale-workflow blocker and template-completion response contract consistency.
      - Legacy route compatibility assertions and monitoring/logging route semantics.
    - Validation gate:
      - `pytest tests/test_web_blueprints_conversion.py -q`
      - `pytest tests/test_survey_preview_regressions.py -q`
      - `./rtk coverage`
  - **PR 3 — Frontend converter modularization + wiring safety**
    - Scope:
      - `app/static/js/modules/converter/*` extractions/delegations.
      - `survey-convert.js` ownership reduction to orchestration shell.
      - Bootstrap/wiring cleanup and stale project-switch reset behavior.
    - Validation gate:
      - `pytest tests/test_converter_workflow_wiring.py -q`
      - `pytest tests/test_backend_monitoring.py -q`
      - `./rtk coverage`
  - **PR 4 — Docs/roadmap + residual compatibility notes (optional, smallest)**
    - Scope:
      - `ROADMAP.md`, workflow audit docs, release notes/compatibility annotations.
    - Validation gate:
      - `./rtk coverage` (sanity)
- Sequential merge order:
  - Merge PR 1 first, rebase remaining PR branches on updated `main`.
  - Merge PR 2 second (contract layer on top of canonical backend helpers).
  - Merge PR 3 third (frontend depends on stabilized backend contracts).
  - Merge PR 4 last (documentation-only and handoff updates).
- Merge checklist per PR:
  - No unresolved `IN PROGRESS` checklist item that belongs to the PR scope.
  - Required focused tests green.
  - Full `./rtk coverage` green (>= 80% fail-under).
  - Short manual smoke: survey prepare -> preview -> convert path.

**Execution snapshot (2026-05-11):**
- Branch status: `survey-workflow-hardening` is clean, synced with upstream, and ahead of `origin/main`.
- Quality gate: full `./rtk coverage` passing at 81.09%.
- Merge strategy: use stacked PR flow below; keep each PR independently releasable.

**Priority 1.35 completion criteria:**
- Stacked PR sequence merged in order (PR1 -> PR2 -> PR3, optional PR4 docs).
- Legacy survey endpoint compatibility surface is explicitly resolved:
  - route old preview/validate endpoints through the unified command adapter, or
  - document and test them as intentional compatibility aliases.
- Final post-merge gate green on `main` (`./rtk coverage` >= 80%).

**Executable stacked PR playbook (exact split from `origin/main..survey-workflow-hardening`):**
- Split uses contiguous commit ranges to minimize reorder risk and conflict churn.
- Range map:
  - **Stack PR 1** (`stack/pr1-survey-modularization-foundation`):
    - `d11360f0^..d8a9e209` (15 commits)
    - Emphasis: frontend converter modularization + early workflow hardening/tests.
  - **Stack PR 2** (`stack/pr2-backend-workflow-service`):
    - `2a5875dd^..871f98b4` (2 commits)
    - Emphasis: backend workflow endpoint consolidation + canonical stage service.
  - **Stack PR 3** (`stack/pr3-contract-hardening-and-polish`):
    - `675c9848^..b43516ed` (4 commits)
    - Emphasis: contract hardening, stale-response normalization, constant ownership cleanup.
- Branch creation commands:
  ```bash
  git fetch origin --prune

  # Stack PR 1
  git switch -c stack/pr1-survey-modularization-foundation origin/main
  git cherry-pick d11360f0^..d8a9e209
  source .venv/bin/activate && ./rtk coverage
  git push -u origin stack/pr1-survey-modularization-foundation

  # Stack PR 2
  git switch -c stack/pr2-backend-workflow-service stack/pr1-survey-modularization-foundation
  git cherry-pick 2a5875dd^..871f98b4
  source .venv/bin/activate && ./rtk coverage
  git push -u origin stack/pr2-backend-workflow-service

  # Stack PR 3
  git switch -c stack/pr3-contract-hardening-and-polish stack/pr2-backend-workflow-service
  git cherry-pick 675c9848^..b43516ed
  source .venv/bin/activate && ./rtk coverage
  git push -u origin stack/pr3-contract-hardening-and-polish
  ```
- PR targeting / merge sequence:
  - Open PR 1: `stack/pr1-survey-modularization-foundation` -> `main`.
  - Open PR 2: `stack/pr2-backend-workflow-service` -> `stack/pr1-survey-modularization-foundation`.
  - Open PR 3: `stack/pr3-contract-hardening-and-polish` -> `stack/pr2-backend-workflow-service`.
  - Merge in order PR1 -> PR2 -> PR3.
  - After each merge, retarget remaining PR base to the newest merged branch (or rebase onto `main` if preferred).
- Conflict handling convention:
  - Resolve conflicts commit-by-commit and continue with `git cherry-pick --continue`.
  - If a range needs restart, use `git cherry-pick --abort` and rerun only the affected range.

**Workflow analysis completed (survey scope):**
- Documented current survey flow and flagged stale/revisited paths in
  `docs/SURVEY_CONVERTER_WORKFLOW_AUDIT_2026-05-09.md`.
- Confirmed active converter entrypoint is `app/static/js/converter-bootstrap.js`
  while legacy converter module paths still exist.
- Identified backend endpoint split (`/api/survey-convert` zip-style legacy path
  vs `/api/survey-convert-validate` JSON workflow path) as a consolidation target.

**Started implementation (backend-first):**
- Moved survey participants schema merge orchestration from frontend JS into
  backend save contract:
  - Added canonical backend helper in `src/participants_backend.py`.
  - Added merge mode handling in
    `app/src/web/blueprints/projects_participants_handlers.py`.
  - Updated survey frontend save flow in
    `app/static/js/modules/converter/survey-convert.js` to send
    `survey_schema_merge_mode` + `survey_selected_schema`.
  - Added regression coverage in
    `tests/test_projects_participants_handlers.py`.

  **Phase 2 progress (entrypoint consolidation):**
  - Updated converter aggregator wiring in
    `app/static/js/modules/converter/index.js` to stop invoking legacy
    `survey.js` quick-import initialization.
  - Added idempotent bootstrap guards in
    `app/static/js/converter-bootstrap.js` and converter aggregator wiring to
    prevent duplicate handler binding if imported through multiple paths.
  - Added wiring assertions in `tests/test_converter_workflow_wiring.py` to
    enforce single bootstrap entrypoint expectations.

  **Phase 3 progress (module extraction, no behavior change):**
  - Extracted survey participant-metadata workflow from
    `app/static/js/modules/converter/survey-convert.js` into new module
    `app/static/js/modules/converter/survey-participants-metadata.js`.
  - Kept `survey-convert.js` as orchestrator and wired it to the extracted
    controller (`createSurveyParticipantsMetadataController`).
  - Extracted survey setup preparation orchestration into
    `app/static/js/modules/converter/survey-workflow-prepare.js` and wired
    `survey-convert.js` to delegate setup/late-blocker/finalization flows through
    `createSurveyWorkflowPrepareController`.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` to assert
    extracted module wiring and backend merge payload contract.
  - Extracted preview orchestration into
    `app/static/js/modules/converter/survey-workflow-preview.js` and delegated
    preview button handling from `survey-convert.js`.
  - Extracted run-progress orchestration into
    `app/static/js/modules/converter/survey-workflow-progress.js` and delegated
    progress state/timer handling from `survey-convert.js`.
  - Extracted survey sourcedata quick-select orchestration into
    `app/static/js/modules/converter/survey-sourcedata-quick-select.js` and
    delegated dropdown refresh/file-load/project-change reset wiring from
    `survey-convert.js`.
  - Extracted template-check orchestration into
    `app/static/js/modules/converter/survey-workflow-template-check.js` and
    delegated check button request/logging/gating/version-wizard branching from
    `survey-convert.js`.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` for
    preview module import/instantiation/delegation and preview endpoint
    ownership assertions.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` for
    progress module import/instantiation/delegation and run-progress API
    ownership assertions.
  - Updated wiring tests in `tests/test_converter_workflow_wiring.py` so
    survey sourcedata endpoint and project-change ownership are asserted in the
    extracted sourcedata module instead of `survey-convert.js`.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` so
    template-check endpoint and project-path append ownership are asserted in
    `survey-workflow-template-check.js`.
  - Extracted template result rendering/save orchestration into
    `app/static/js/modules/converter/survey-template-results.js` and delegated
    template result mode dispatch from `survey-convert.js` to
    `createSurveyTemplateResultsController`.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` to
    assert template-results import/instantiation/delegation and endpoint
    ownership (`/api/limesurvey-save-to-project` and `/api/library-template/`).
  - Extracted shared survey value-offset parsing/normalization helpers into
    `app/static/js/modules/converter/survey-value-offset-utils.js` and reduced
    duplicate helper ownership in `survey-convert.js` to thin wrappers.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` for the
    new value-offset utility module and `survey-convert.js` delegation wrappers.
  - Extracted value-offset editor apply-state and DOM event wiring into
    `app/static/js/modules/converter/survey-value-offset-editor.js` and
    delegated from `survey-convert.js` via
    `createSurveyValueOffsetEditorController` while keeping existing offset
    state/review logic in the orchestrator.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` to
    assert value-offset editor controller import/instantiation/initialization
    and ownership of add-row/change/input/remove bindings.
  - Shifted value-offset status/signature helper ownership
    (`hasManualTaskValueOffsets`, `hasAppliedTaskValueOffsetSelections`,
    `updateTaskValueOffsetApplyState`, and related map/signature helpers) into
    `survey-value-offset-editor.js`, with `survey-convert.js` now delegating
    through thin wrappers.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` to
    assert helper delegation in `survey-convert.js` and helper ownership in the
    extracted value-offset editor controller.
  - Moved value-offset editor state mutation/render internals
    (`createTaskValueOffsetRow`, row rendering, text/state sync, ensure/focus,
    and editor-change handlers) into
    `app/static/js/modules/converter/survey-value-offset-editor.js`.
  - Reduced `survey-convert.js` value-offset UI functions to thin delegation
    wrappers and injected dependencies (task list provider, row-id allocator,
    parser/normalizer utilities, and escape helper) into the controller.
  - Extended wiring tests in `tests/test_converter_workflow_wiring.py` to
    assert delegation wrappers in `survey-convert.js` and row-markup ownership
    (`data-role="operator"`, `data-role="magnitude"`) in the extracted
    value-offset editor controller.
  - Moved available-task derivation and manual-offset retrieval helper ownership
    (`getAvailableSurveyTasksForValueOffsets`, `getManualTaskValueOffsets`)
    into `survey-value-offset-editor.js`, with `survey-convert.js` keeping
    thin delegation wrappers.
  - Updated controller wiring to inject preview-selection/template-version/
    preview-task providers instead of calculating those lists directly inside
    `survey-convert.js`.
  - Moved manual offset apply-click behavior (`convertApplyValueOffsetsBtn`)
    into `survey-value-offset-editor.js` via
    `handleApplyTaskValueOffsetsClick`, keeping `survey-convert.js` as a thin
    event-binding delegator.
  - Extended controller wiring with `getTemplateWorkflowGate` + `convertInfo`
    so offset-apply gate-clearing/message behavior remains centralized in the
    editor controller without changing workflow semantics.
  - Updated `tests/test_converter_workflow_wiring.py` to assert apply-click
    delegation ownership moved out of `survey-convert.js`.
  - Moved version-wizard apply-click behavior (`surveyVersionWizardApplyBtn`)
    into `survey-workflow-template-check.js`
    (`handleVersionWizardApplyClick`) while keeping `survey-convert.js` as a
    thin event-binding delegator.
  - Extended template-check controller wiring with narrow selection-state
    callbacks (`hasMultiVersionWizardTasks`,
    `hasCompleteVersionWizardSelections`,
    `getCurrentTemplateVersionSelectionSignature`,
    `setAppliedTemplateVersionSelectionSignature`,
    `setVersionWizardRetryGateMode`, and template-gate/action-state accessors)
    to preserve behavior without duplicating orchestration logic.
  - Updated `tests/test_converter_workflow_wiring.py` to assert version-wizard
    apply ownership in the template-check controller and prevent reintroducing
    inline apply branching in `survey-convert.js`.
  - Moved `surveyVersionWizardApplyBtn` click-event binding into
    `survey-workflow-template-check.js` `initialize()`, so both template-check
    and version-apply interactions are owned by one workflow controller.
  - Removed redundant version-apply listener wiring from
    `survey-convert.js`, leaving the orchestrator free of this UI event
    registration.
  - Extracted preview/conversion summary rendering and selection-binding
    behavior from `survey-convert.js` into new module
    `app/static/js/modules/converter/survey-conversion-summary.js` via
    `createSurveyConversionSummaryController`.
  - Reduced `survey-convert.js` summary ownership to thin delegation
    (`displayConversionSummary`) and injected narrow state callbacks
    (`getSurveyPreviewSelectionState`, `setSurveyPreviewSelectedTasks`) plus
    formatter/UI helpers into the summary controller.
  - Updated `tests/test_converter_workflow_wiring.py` to assert summary module
  - Extracted conversion-result application from
    `app/static/js/modules/converter/survey-workflow-convert.js` into new
    module `app/static/js/modules/converter/survey-workflow-convert-results.js`
    so the convert workflow controller now delegates validation/save-summary/
    participant-registry result handling through
    `createSurveyWorkflowConvertResultsController`.
  - Removed unreachable survey-library/template-check DOM branches from
    `app/static/js/modules/converter/survey-convert.js` and matching stale
    bootstrap wiring in `app/static/js/converter-bootstrap.js`
    (`convertLibraryPath`, `convertBrowseLibraryBtn`,
    `checkProjectTemplatesBtn`, `surveyI18nWarning`,
    `surveyStructureWarning`).
  - Added unified backend adapter endpoint
    `POST /api/survey-workflow-command` in
    `app/src/web/blueprints/conversion_survey_handlers.py` and switched the
    survey workflow prepare/preview/convert frontend modules to use that one
    command endpoint with explicit `workflow_command` values while keeping the
    legacy routes mounted as compatibility aliases.
  - Extended focused coverage in `tests/test_converter_workflow_wiring.py`,
    `tests/test_web_blueprints_conversion.py`, and
    `tests/test_backend_monitoring.py` for the new convert-results controller,
    stale survey UI cleanup, unified workflow-command route dispatch, and
    backend monitoring command rendering.
  - Extended workflow-command adapter regression coverage in
    `tests/test_web_blueprints_conversion.py` for alias value/field dispatch
    (`setup`, `dry_run`, `validate`, plus `command`/`mode` payload aliases)
    so frontend/backend command consolidation stays stable.
  - Added template-version override shape-preservation regression coverage in
    `tests/test_survey_template_version_persistence.py` to pin request payload
    passthrough behavior when project-level selections are absent.
  - Hardened unified workflow-command parsing in
    `app/src/web/blueprints/conversion_survey_handlers.py` so
    `/api/survey-workflow-command` now also accepts JSON payload aliases
    (`workflow_command` / `command` / `mode`) while preserving existing form
    precedence.
  - Extended regression coverage in `tests/test_web_blueprints_conversion.py`
    for JSON workflow-command dispatch and form-over-JSON precedence, and in
    `tests/test_survey_preview_regressions.py` to pin non-redundant preview
    validation execution (single dry-run preview + single full validation pass)
    when no manual-review exception contract is configured.
  - Lessons learned: workflow command adapters should parse both multipart and
    JSON request shapes to avoid transport-coupled regressions; preview
    validation coverage should explicitly assert run-count semantics for
    multi-task results to catch accidental per-task reruns early.
  - Extracted shared survey stage-form parsing into backend service
    `src/survey_workflow_service.py` (`parse_stage_form_fields`) and switched
    both `api_survey_convert` and `api_survey_convert_validate` in
    `app/src/web/blueprints/conversion_survey_handlers.py` to delegate
    id/session/run/sheet/unknown/name/language/strict-levels/near-match/duplicate
    parsing through that canonical backend helper.
  - Added focused backend parser coverage in
    `tests/test_survey_workflow_service.py` for normalization/default/fallback
    behavior, and revalidated endpoint compatibility in
    `tests/test_web_blueprints_conversion.py`.
  - Coverage checkpoint: `./rtk coverage` now passes at 81.03%
    (1986 passed, 3 skipped), clearing the interim 80% gate with margin.
  - Lessons learned: request-shape extraction is low-risk when endpoint-specific
    save/archive semantics stay in adapters while common stage parsing is
    centralized in backend service helpers.
  - Extended `parse_stage_form_fields` backend reuse to
    `api_survey_check_project_templates` and
    `api_survey_detect_version_context` in
    `app/src/web/blueprints/conversion_survey_handlers.py`, removing remaining
    duplicate id/session/run/sheet/duplicate normalization blocks from these
    adapter routes.
  - Revalidated detect/check-project-template workflow contracts with focused
    endpoint tests in `tests/test_web_blueprints_conversion.py` and
    `tests/test_converter_project_context_helpers.py`; full gate remains
    stable at 81.03% coverage.
  - Lessons learned: small parser reuse increments across adjacent routes keep
    behavior stable while making backend-owned normalization easier to expand
    into preview/prepare paths next.
  - Extracted stale-workflow blocker payload assembly into canonical backend
    helpers in `src/survey_workflow_service.py`
    (`build_near_match_confirmation_payload`,
    `build_template_completion_required_payload`) and switched
    `api_survey_convert` / `api_survey_convert_validate` to delegate near-match
    and template-completion preflight payload creation through those helpers.
  - Reused the backend near-match payload helper in
    `app/src/web/blueprints/conversion_survey_preview_handlers.py` so
    prepare/preview/convert now share one canonical near-match blocker message
    contract.
  - Added focused helper regression tests in
    `tests/test_survey_workflow_service.py` and revalidated stale-preparation
    blocker endpoint behavior in `tests/test_web_blueprints_conversion.py` and
    `tests/test_survey_preview_regressions.py`.
  - Coverage checkpoint: `./rtk coverage` now passes at 81.05%
    (1988 passed, 3 skipped, 2 warnings).
  - Lessons learned: keep stale-workflow wrapping (prepared-workflow
    translation/log attachment) in web adapters, but centralize reusable
    blocker payload construction in backend service helpers.
  - Centralized stale-preparation response transformation in backend helper
    `SurveyWorkflowStageService.format_workflow_preparation_stale_response`
    (`src/survey_workflow_service.py`) and reduced
    `app/src/web/blueprints/conversion_survey_preview_handlers.py`
    `_format_workflow_preparation_stale_response(...)` to a thin adapter that
    only resolves request context (`prepared_workflow`) and delegates.
  - Added service-level regression coverage in
    `tests/test_survey_workflow_service.py` for wrapped vs non-wrapped stale
    payload behavior (including log passthrough), and revalidated stale-blocker
    contracts in `tests/test_web_blueprints_conversion.py` and
    `tests/test_survey_preview_regressions.py`.
  - Coverage checkpoint: `./rtk coverage` now passes at 81.08%
    (1990 passed, 3 skipped, 2 warnings).
  - Lessons learned: pure stale-response transformation belongs in backend
    helpers; web adapters should only supply request-derived flags and keep
    transport concerns local.
  - Decoupled `app/src/web/blueprints/conversion_survey_handlers.py` from
    preview-layer private stale wrapper import by adding local adapter helpers
    (`_is_prepared_workflow_request`,
    `_format_workflow_preparation_stale_response`) that delegate directly to
    `SurveyWorkflowStageService.format_workflow_preparation_stale_response`.
  - Added handler-level regression coverage in
    `tests/test_web_blueprints_conversion.py` for prepared vs unprepared stale
    wrapper behavior (including log passthrough), while keeping existing stale
    blocker endpoint tests green.
  - Coverage checkpoint: `./rtk coverage` now passes at 81.08%
    (1992 passed, 3 skipped, 2 warnings).
  - Lessons learned: avoid cross-module imports of private web helpers;
    each adapter can keep tiny request-context wrappers that call canonical
    backend service logic.
  - Centralized prepared-workflow boolean parsing in backend helper
    `SurveyWorkflowStageService.parse_prepared_workflow_flag` and switched both
    `app/src/web/blueprints/conversion_survey_handlers.py` and
    `app/src/web/blueprints/conversion_survey_preview_handlers.py` wrappers to
    delegate this truthy/falsey normalization instead of duplicating inline
    string checks.
  - Added focused parser regression coverage in
    `tests/test_survey_workflow_service.py` for canonical truthy and falsey
    prepared-workflow values; stale-wrapper endpoint tests remain green.
  - Coverage checkpoint: `./rtk coverage` remains at 81.08%
    (1994 passed, 3 skipped, 2 warnings).
  - Lessons learned: keep all request-flag normalization in backend helpers so
    adapter wrappers only read request fields and forward normalized booleans.
  - Promoted survey input-format constants to canonical backend ownership in
    `src/survey_workflow_service.py`
    (`SUPPORTED_SURVEY_TABULAR_SUFFIXES`,
    `SUPPORTED_SURVEY_INPUT_SUFFIXES`,
    `SUPPORTED_SURVEY_INPUT_MESSAGE`) and rewired both
    `app/src/web/blueprints/conversion_survey_preview_handlers.py` and
    `app/src/web/blueprints/conversion_survey_handlers.py` to consume those
    shared constants instead of cross-importing preview-private constants.
  - Kept preview-module compatibility aliases (`_SUPPORTED_*`) intact so
    existing route behavior and imports remain stable while ownership moved to
    backend service.
  - Added service-level constant coverage in
    `tests/test_survey_workflow_service.py` and revalidated survey preview /
    validate / version-context / project-template-check endpoint groups.
  - Coverage checkpoint: `./rtk coverage` now passes at 81.09%
    (1995 passed, 3 skipped, 2 warnings).
  - Lessons learned: shared format-policy constants should live in backend
    service modules; web adapters can expose local aliases for compatibility
    but should not own canonical values.
  - Reused canonical backend workflow stage execution in preview flow by routing
    dry-run preview, per-task validation probes, and full preview validation
    passes through `SurveyWorkflowStageService.run_stage` in
    `app/src/web/blueprints/conversion_survey_preview_handlers.py`.
  - Preserved existing preview contract behavior while consolidating dispatch:
    tabular requests keep effective template overrides, `.lsa` keeps raw
    request-shaped overrides, and `near_match_tasks` payload type is preserved
    (preventing set->list regression in allowlist forwarding).
  - Revalidated with focused regression suites:
    `tests/test_survey_preview_regressions.py`,
    `tests/test_survey_value_offsets.py`, and
    `tests/test_web_blueprints_conversion.py` (preview/prepare/version-context
    groups), with full `./rtk coverage` still green at 81.09%.
  - Lessons learned: backend stage-service reuse in preview is safe when
    payload-shape compatibility (especially override and allowlist types) is
    explicitly preserved and pinned by regression tests.
  - Summary and validation-results module extraction wiring is complete and
    covered by focused wiring assertions, keeping summary/validation specific
    UI behavior owned by extracted modules instead of `survey-convert.js`.
  - Confirmed legacy `POST /api/survey-convert` route is still mounted for
    compatibility; current survey workflow now uses
    `POST /api/survey-workflow-command` for prepare/preview/convert dispatch.
  - Added canonical backend survey workflow stage service in
    `src/survey_workflow_service.py` and switched
    `api_survey_convert` / `api_survey_convert_validate` to delegate effective
    survey-library fallback plus preflight/convert engine dispatch through that
    one backend service while preserving existing Flask response shaping.
  - Reduced the largest remaining backend duplication from engine dispatch to
    request/form parsing and response assembly inside
    `app/src/web/blueprints/conversion_survey_handlers.py`.
  - Extracted conversion-log behavior from `survey-convert.js` into a dedicated
    controller/module with wiring coverage to prevent ownership drift.

**Remaining work (Priority 1.35):**
- [x] Move shared survey request/form parsing + stale-workflow shaping into backend helpers under `src/`.
- [x] Reuse canonical stage-service execution in preview paths so dispatch/fallback rules align across prepare/preview/convert.
- [ ] Reduce legacy compatibility surface by routing old survey preview/validate endpoints through the unified command adapter or documenting them as explicit tested aliases.
  - Hardened survey project-switch reset handling in
    `app/static/js/modules/converter/survey-convert.js` so
    `prism-project-changed` clears project-bound survey selection state
    (hidden file input plus sourcedata quick-select), resets version-wizard
    retry/apply state, clears stale manual-offset guidance, and drops stale
    preview/conversion UI before the next project workflow.
  - Extended `tests/test_converter_workflow_wiring.py` to assert the
    project-change reset contract and prevent stale survey selection/version
    state from surviving project switches.
  - Extracted unmatched-template error rendering/save orchestration from
    `survey-convert.js` into
    `app/static/js/modules/converter/survey-unmatched-templates.js` via
    `createSurveyUnmatchedTemplatesController`.
  - Reduced `survey-convert.js` unmatched-template ownership to thin
    delegation (`displayUnmatchedGroupsError`) and controller initialization
    for save handlers (`window.saveUnmatchedTemplate`,
    `window.saveAllUnmatchedTemplates`).
  - Extracted import/reset form-state behavior from `survey-convert.js` into
    `app/static/js/modules/converter/survey-import-form-state.js` via
    `createSurveyImportFormStateController` while keeping
    `resetSurveyImportFormState(...)` as a thin wrapper in the orchestrator.
  - Extracted near-item-match candidate parsing and selection modal UI from
    `survey-convert.js` into
    `app/static/js/modules/converter/survey-near-item-match-review.js` via
    `createSurveyNearItemMatchReviewController`.
  - Reduced `survey-convert.js` near-item-match ownership to thin delegation
    wrappers (`collectNearMatchCandidates`,
    `buildNearMatchConfirmationMessage`, `promptNearMatchSelection`) and wired
    controller initialization after shared helper setup.
  - Updated `tests/test_converter_workflow_wiring.py` to assert near-item-match
    review module import/instantiation/delegation and prevent the modal markup
    from drifting back into `survey-convert.js`.
  - Extracted shared survey workflow response helpers from
    `survey-convert.js` into
    `app/static/js/modules/converter/survey-workflow-response-utils.js`
    (`summarizeServerResponseText`, `parseJsonResponse`).
  - Kept `survey-convert.js` response helpers as thin wrappers delegating to the
    extracted workflow-response utils module so downstream controller contracts
    stayed stable.
  - Extended `tests/test_converter_workflow_wiring.py` to assert
    workflow-response util module ownership and guard against JSON response
    parsing logic drifting back into `survey-convert.js`.
  - Extracted version-context normalization/sorting helpers from
    `survey-convert.js` into
    `app/static/js/modules/converter/survey-version-context-utils.js`
    (`normalizeVersionSelectionSession`, `normalizeVersionSelectionRun`,
    `buildVersionSelectionKey`, timeline comparators, and
    `deriveDetectedContexts`).
  - Kept `survey-convert.js` helper signatures as thin delegates to
    version-context utils so version-wizard orchestration callsites and injected
    controller dependencies remained stable.
  - Extended `tests/test_converter_workflow_wiring.py` to assert
    version-context util module ownership and orchestrator import wiring.
  - Extracted project-save/participant-registry feedback helpers from
    `survey-convert.js` into
    `app/static/js/modules/converter/survey-convert-feedback.js` via
    `createSurveyConvertFeedbackController`.
  - Reduced `survey-convert.js` ownership for `getProjectSaveSummary`,
    `openConverterTab`, `showConvertInfoMessage`,
    `getParticipantRegistryWarning`, and `showParticipantRegistryWarning` to
    thin delegation wrappers.
  - Updated `tests/test_converter_workflow_wiring.py` to assert feedback module
    import/ownership and adjusted save-path surface assertions to track the
    extracted module rather than the orchestrator.
  - Extracted survey file-separator helpers from `survey-convert.js` into
    `app/static/js/modules/converter/survey-file-separator-utils.js`
    (`isDelimitedSurveyFilename`, `getSelectedSeparator`,
    `updateSeparatorVisibility`).
  - Reduced `survey-convert.js` separator helpers to thin delegation wrappers,
    preserving existing callsites and UI behavior.
  - Extended `tests/test_converter_workflow_wiring.py` to assert
    separator-utils module ownership and orchestrator import wiring.
  - Fixed convert setup task-scoping regression: convert workflow now forwards
    selected survey tasks into the setup (`prepare`) request payload so
    preflight/manual-offset blockers only evaluate the user-selected surveys.
  - Updated survey workflow modules and wiring tests to enforce selected-task
    propagation through setup (`selectedTasks: selectedSurveyTasks` in convert
    flow and `selected_tasks` form payload support in workflow request builder).
  - Moved Step 4-5 action controls (Preview/Convert + run progress + cancel)
    to the bottom workflow section in `converter_survey.html`, directly below
    conversion summary, so users no longer need to scroll back up to run
    Convert after preview review.
  - Fixed survey workflow runtime crash (`dictionary update sequence element #0
    has length 4; 2 is required`) by preserving list-based
    `template_version_overrides` in `src/survey_workflow_service.py` instead of
    coercing all overrides through `dict(...)`.
  - Added regression coverage in `tests/test_survey_workflow_service.py` for
    list- and dict-shaped `template_version_overrides` forwarding.
  - Fixed backend selected-task scoping gap in
    `api_survey_convert_validate`: the endpoint now parses `selected_tasks`
    and merges it with `survey` filter input so convert preflight and final
    run only evaluate user-selected surveys.
  - Added regression coverage in
    `tests/test_web_blueprints_conversion.py` to assert
    `api_survey_convert_validate` merges `survey` + `selected_tasks` and
    forwards the narrowed filter (`pss` in a `pss,gad` + selected `pss`
    scenario) through both preflight and convert runs.
  - Reframed out-of-range workflow messaging (backend + frontend) to manual-
    fix-first guidance: correct source values first, keep task value offsets as
    an optional advanced fallback rather than the default implied action.
  - Restored LimeSurvey sidecar source gating in survey conversion backend
    (`app/src/converters/survey.py` and `src/converters/survey.py`):
    `tool-limesurvey` column extraction and sidecar writes now run only for
    native LimeSurvey imports (`source_format` in `lsa`/`lss`), preventing
    non-LimeSurvey CSV/XLSX/TSV imports from emitting
    `*_tool-limesurvey_survey.json` sidecars that fail PRISM schema checks
    (`'Technical' is a required property`).
  - Improved validation error UX in
    `app/static/js/modules/converter/survey-validation-results.js`:
    repeated file-level errors now collapse by issue kind (path-insensitive,
    e.g. shared `schema error: 'Technical' is a required property`) so large
    PRISM301 batches render as one expandable section instead of long duplicate
    lists.
  - Added static wiring regression assertions for the new validation collapse
    helper (`extractValidationIssueKind`) in
    `tests/test_converter_workflow_wiring.py`.
  - Added backend stale-artifact cleanup in
    `api_survey_convert_validate` save flow: for non-LimeSurvey imports,
    touched survey folders now remove leftover
    `*_tool-limesurvey_survey.{tsv,json}` files from earlier buggy runs so
    obsolete sidecars do not keep failing project validation.
  - Added endpoint regression coverage in
    `tests/test_web_blueprints_conversion.py` to assert stale
    `tool-limesurvey` sidecars are removed during non-LSA convert-validate
    saves.
  - Extracted unmatched-template error rendering/save orchestration from
    `survey-convert.js` into new module
    `app/static/js/modules/converter/survey-unmatched-templates.js` via
    `createSurveyUnmatchedTemplatesController`.
  - Reduced `survey-convert.js` unmatched-template ownership to thin
    delegation (`displayUnmatchedGroupsError`) and controller initialization
    for save handlers (`window.saveUnmatchedTemplate`,
    `window.saveAllUnmatchedTemplates`).
  - Updated `tests/test_converter_workflow_wiring.py` to assert unmatched-
    template module import/instantiation/delegation and to prevent legacy
    window-handler/save-loop logic from drifting back into `survey-convert.js`.
  - Improved questionnaire version wizard UX in
    `app/static/js/modules/converter/survey-convert.js` by adding a default
    shared-selection mode (`Use one version for all sessions/runs`) with
    explicit per-context override, while preserving session/run-level
    selections in `selectedTemplateVersions`.
  - Improved questionnaire version wizard readability in
    `app/templates/converter_survey.html` and
    `app/static/css/converter.css` using dedicated contrast classes
    (`survey-version-card`, custom meta/count/variant badges) instead of
    low-contrast generic alert/muted combinations.
  - Extended wiring regression checks in
    `tests/test_converter_workflow_wiring.py` for shared-selection mode hooks
    and updated wizard template class wiring.
  - Added RTK-first coverage workflow tooling:
    - `rtk coverage` now runs `pytest` with `--cov=src`,
      `--cov-report=term-missing`, `--cov-report=xml`, and default
      `--cov-fail-under=80` (interim target).
    - `rtk codecov` now forwards to `codecovcli` for optional coverage uploads.
    - Added `codecov-cli` to development dependencies and documented new RTK
      coverage/codecov commands in `README.md` and `docs/CLI_REFERENCE.md`.
  - Added coverage-scope excludes in `pyproject.toml` for non-core ops scripts
    (`maintenance/*`, `bids_file_deleter.py`, `runtime_dependencies.py`) to
    keep the interim gate focused on actively maintained runtime surfaces.
  - Verified interim coverage target: `./rtk coverage` reports **80.96%** total
    coverage for `src/` after scope alignment (above interim 80% target).
  - Cleared packaged-web regression failures in
    `tests/test_packaged_web_optional_blueprints.py` by guarding
    `prism_static_asset_token` defaults in `app/templates/base.html`.
  - Cleared the remaining full-suite `rtk coverage` blockers by fixing:
    - multiversion context-map edge cases in
      `src/converters/survey.py` (single-session override context retention
      and run-count derivation from detected run values),
    - direct-call signature compatibility and manual-review validation guarding
      in
      `app/src/web/blueprints/conversion_survey_preview_handlers.py`,
    - survey schema acceptance of empty `Technical.SoftwarePlatform` placeholders
      in `app/schemas/v0.2/survey.schema.json` and
      `app/schemas/stable/survey.schema.json`.
  - Revalidated end-to-end: `./rtk coverage` now exits cleanly with
    **1978 passed, 3 skipped** at **80.96%** coverage.

  **Assessment update (2026-05-10):**
  - Confirmed stale DOM-guarded branches still exist in `survey-convert.js`
    for controls no longer present in `converter_survey.html`
    (template-check button, i18n/structure warning containers, library path
    picker controls).
  - Confirmed legacy `POST /api/survey-convert` route is still mounted for
    compatibility while current frontend workflow uses
    `POST /api/survey-convert-validate`.
  - Identified convert-run handler as the primary remaining monolith and next
    extraction target.
  - Resolved project-switch stale-state risk: survey tab now clears
    project-bound survey selection and version-gate state on
    `prism-project-changed` before the next preview/convert cycle.

**Next steps:**
- Consolidate converter survey entrypoints and remove unreachable legacy survey
  quick-import module paths.
- Split monolithic survey converter frontend into workflow-step modules
  (prepare, preview, convert, participant-metadata).
- Introduce one backend workflow command endpoint for preview/convert state
  transitions so the frontend becomes a thin state renderer.
- Raise and hold repository coverage above 90% (`src/`) using `rtk coverage`,
  then upload `coverage.xml` via `rtk codecov upload-process` in CI.

**Lessons learned:**
- Backend-first merge contracts reduce frontend state drift and avoid duplicate
  merge logic in browser code.
- Survey workflow complexity now comes more from feature accretion than missing
  capability; incremental extraction with strict backend ownership is safer than
  a rewrite.
- A backend service extraction is safest when it preserves the existing wrapper
  contract first; calling raw converters directly dropped fallback behavior and
  endpoint tests caught that immediately.
- Extraction patches in `survey-convert.js` should be applied in small hunks:
  large monolith deletions can leave orphan fragments that focused wiring tests
  catch quickly.
- Shared offset parsing/formatting helpers are low-risk extraction targets that
  reduce drift across preview/convert/manual-offset code paths before moving
  larger stateful editor orchestration.
- Extracting stateful editor wiring as a controller is a safe intermediate step:
  keep one orchestrator-owned state model first, then move state and business
  rules only after wiring tests pin behavior.
- Status/signature helper extraction is a good next micro-step after event
  wiring extraction: it trims orchestrator logic while preserving one shared
  editor state model and minimizes behavior risk.
- After wiring + status delegation, moving render/state helpers is still safe
  if one shared state store remains in the orchestrator and the controller is
  injected with narrow callbacks for state access and id allocation.
- The same injection pattern also works for cross-context task availability:
  pass preview/template providers into the controller to avoid duplicating list
  derivation while keeping workflow state ownership centralized.
- The same approach also works for late-stage button-click extraction: keep one
  orchestrator event binding, move branching behavior into the controller, and
  inject narrow gate/message accessors instead of shifting workflow state
  ownership.
- Version-selector apply behavior is a good fit for the template-check module:
  move click branching there first, keep shared state in the orchestrator, and
  wire explicit getter/setter callbacks for apply signatures and retry gates.
- Once branching is extracted, moving the corresponding click binding into the
  same controller further reduces orchestration surface area with minimal risk.
- The conversion summary block is a safe extraction unit when done as one
  controller: keep preview selection state in the orchestrator and expose only
  narrow getter/setter callbacks to avoid workflow-state drift.
- Validation rendering is another safe extraction unit: keep DOM/state entry
  points in the orchestrator and move formatting/grouping details behind a
  single controller interface.
- Conversion-log behavior is also safe to extract as one controller when the
  orchestrator still owns workflow sequencing and only delegates append/reset
  operations plus UI toggle initialization.
- Unmatched-template save flows with inline `onclick` hooks can still be
  extracted safely: keep global handler registration in one controller
  `initialize()` method and delegate the rendering/POST/save-state logic there.
- If workflow options can arrive as multiple shapes (dict vs list-of-dicts),
  backend stage services must preserve shape instead of blindly coercing with
  `dict(...)`; converter-facing payload tests catch these regressions early.
- Near-item-match review UX can be extracted safely when the orchestrator keeps
  only delegation wrappers and the dedicated controller owns both modal and
  non-modal fallback confirmation behavior.
- Generic workflow response parsing/sanitization logic is a stable extraction
  target: move it to a shared converter util module while keeping orchestrator
  wrapper signatures intact so controller dependencies remain unchanged.
- Version-selection context math (session/run normalization, timeline sort
  ordering, and detected-context derivation) is another stable extraction
  target because it is side-effect free and can be wrapped without behavior
  changes in workflow orchestration.
- Converter post-run user feedback (project output summary and participants TSV
  warning CTA routing) can be extracted into a dedicated controller without
  workflow behavior changes when the orchestrator keeps only delegation
  wrappers.
- Small deterministic helper clusters (like file-separator gating) are good
  extraction slices: move to utility modules first, then keep wrappers in
  orchestrator to avoid broad callsite churn.
- If conversion supports per-task deselection, setup/preflight requests must be
  scoped with the same selected task set as final convert requests; otherwise
  out-of-range blockers can fire for tasks the user explicitly deselected.
- Workflow convert-validate handlers must apply the same selected-task merge as
  preview/convert handlers; missing it in one adapter endpoint is enough to
  reintroduce deselected-task blockers even when frontend payloads are correct.
- Out-of-range handling copy should default to source-data correction guidance;
  manual value offsets are an optional recovery path, not the primary expected
  resolution for typical single-item coding mistakes.
- Tool-specific sidecar emission must stay source-aware: if `tool-limesurvey`
  extraction is not gated to native LimeSurvey inputs (`lsa`/`lss`), regular
  tabular imports can emit false `*_tool-limesurvey_*` artifacts and trigger
  cascading PRISM301 schema errors.
- Validation duplication often differs only in file-path prefixes; collapsing by
  issue kind (for example normalized `schema error: ...`) keeps large PRISM301
  batches readable without hiding actionable file lists.
- Source-format gating alone is not enough after prior buggy saves: non-LSA
  save flows should also clean stale `tool-limesurvey` artifacts in touched
  survey folders to prevent legacy false errors from persisting across runs.
- Project-change handlers for sourcedata-backed inputs must clear both the
  visible quick-select and the underlying file input; clearing only one leaves
  the next project coupled to stale source state.
- A thin adapter route is a low-risk first step for backend command
  consolidation: switch the frontend to one endpoint first, keep legacy routes
  as aliases, then collapse duplicated backend handler logic behind that
  adapter instead of rewriting both layers at once.
- Multi-context version selection should default to a single shared choice for
  ease of use, then allow explicit per-session/run overrides only when users
  need longitudinal scale differences.
- Coverage goals are easiest to enforce when wired into one canonical command
  (`rtk coverage`) with a fail-under gate and CI upload path, instead of ad hoc
  local pytest flags.
- Per-task preview validation probes should run only when an explicit
  out-of-bounds exception contract is configured; otherwise preview workflows
  can duplicate conversion passes and drift call-count behavior in regression
  tests.

