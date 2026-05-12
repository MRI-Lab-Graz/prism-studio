# PRISM Studio - Roadmap

Last updated: 2026-05-12

## Current Mission

Sequentially merge survey-workflow-hardening into main using a stacked PR flow.
This is the top delivery goal for the current cycle.

## Status Board

| Priority | Title | Status | Next Action |
|---|---|---|---|
| 1.35 | Survey converter workflow hardening and backend command consolidation | IN PROGRESS | Execute stacked PR merge sequence to main |
| 1.26 | UI harmonization and beginner-help improvements | IN PROGRESS | Finish remaining page migrations to shared UI primitives |
| 2 | Export anonymization: participant ID renaming | TODO | Implement JSON/TSV/path replacement pass in export flow |
| 3 | JSON tag stripping and NIfTI GZIP header cleaning | DEFERRED | Revisit after Priority 2 is complete |

## Active Work

### Priority 1.35 - Survey converter workflow hardening and backend command consolidation

Goal: reduce survey converter complexity and finish safe merge to main via ordered stacked PRs.

Current state:
- Working branch: survey-workflow-hardening.
- Branch state at last check: ahead of origin/main by 21 commits, behind by 0, clean worktree.
- Latest full quality gate: ./rtk coverage passing at 81.09%.
- Frontend survey workflow is already moved to unified backend command routing (/api/survey-workflow-command) with legacy endpoints kept as compatibility aliases.

What is already completed:
- Backend canonical service extraction in src/survey_workflow_service.py for shared parsing, stale-response shaping, and stage execution helpers.
- Frontend survey converter extraction into dedicated modules under app/static/js/modules/converter/ with orchestrator slimming.
- Unified command adapter route added and wired across prepare/preview/convert paths.
- Focused regression coverage expanded for workflow wiring, preview contracts, stale wrappers, and command dispatch aliases.
- Full-suite coverage remains above fail-under threshold (80%).
- Survey workflow request payloads now propagate explicit project_path across prepare/preview/convert paths.
- Backend survey preview and convert-validate paths now prefer explicit project_path and reject stale explicit paths before conversion stages.
- New workflow-endpoint contract coverage added for stale explicit project rejection and explicit project precedence under /api/survey-workflow-command.
- Added backend src compatibility bridge for `src._compat` so mirrored app converter shims load reliably in repo-root runtime as well as app runtime.
- Added repo-runtime shim regression coverage in tests/test_compat_loader.py to prevent future adapter import drift.

Latest checkpoint (2026-05-12):
- Completed implementation slice: explicit project-path hardening for survey workflow frontend and backend.
- Completed implementation slice: repo/runtime compatibility hardening for converter shims via backend `src._compat` bridge.
- Focused suites green:
  - ./rtk test tests/test_converter_workflow_wiring.py tests/test_converter_project_save_contracts.py tests/test_compat_loader.py
  - ./rtk test tests/test_web_blueprints_conversion.py -k "test_api_survey_convert_blocks_until_templates_completed or test_api_survey_convert_forwards_template_version_overrides or test_api_survey_convert_registers_detected_sessions_for_all"

Lessons learned:
- For workflow refactors, project context must be treated as request-scoped data; relying on session-only context is fragile for multi-tab and delayed-switch flows.
- Contract tests should exercise the unified adapter endpoint (/api/survey-workflow-command), not only legacy alias endpoints, to catch integration drift early.
- Run at least one broader targeted blueprint subset after endpoint refactors; this quickly surfaces NameError/scope regressions that focused wiring tests can miss.
- Mirrored shims should be tested in both app-root and repo-root import contexts; one-sided runtime tests can miss `src._compat` resolution failures.
- Keep RTK-first discipline for repo validation (`./rtk test ...`), so CI/local command surfaces stay aligned before PR creation.

#### Stacked PR Playbook (execution target)

Split strategy uses contiguous commit ranges from origin/main..survey-workflow-hardening.

- Stack PR 1 (stack/pr1-survey-modularization-foundation)
  - Range: d11360f0^..d8a9e209 (15 commits)
  - Focus: frontend modularization foundation plus early workflow hardening/tests.

- Stack PR 2 (stack/pr2-backend-workflow-service)
  - Range: 2a5875dd^..871f98b4 (2 commits)
  - Focus: backend workflow endpoint consolidation and canonical stage service.

- Stack PR 3 (stack/pr3-contract-hardening-and-polish)
  - Range: 675c9848^..b43516ed (4 commits)
  - Focus: contract hardening, stale-response normalization, constants cleanup.

Branch creation commands:

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

PR targeting and merge order:
1. Open PR 1: stack/pr1-survey-modularization-foundation -> main.
2. Open PR 2: stack/pr2-backend-workflow-service -> stack/pr1-survey-modularization-foundation.
3. Open PR 3: stack/pr3-contract-hardening-and-polish -> stack/pr2-backend-workflow-service.
4. Merge in strict order: PR1 -> PR2 -> PR3.

Completion criteria:
- Stacked PR sequence merged in order (PR1 -> PR2 -> PR3).
- Legacy survey endpoint compatibility is explicitly finalized:
  - either route old preview/validate endpoints through unified command adapter, or
  - keep them as intentional tested aliases with clear contract ownership.
- Post-merge full gate on main remains green (./rtk coverage >= 80%).

Immediate next actions:
1. Create stack/pr1-survey-modularization-foundation from origin/main and cherry-pick PR1 range.
2. Run focused tests and ./rtk coverage on PR1, then open PR1.
3. Repeat for PR2 and PR3 with strict retargeted stacked bases.
4. Merge sequentially and re-run post-merge gate on main.

Detailed implementation log moved to:
- docs/SURVEY_WORKFLOW_HARDENING_2026.md

### Priority 1.26 - UI harmonization and beginner-help improvements

Goal: unify page-shell and file-input UX while preserving PRISM branding and keeping backend behavior unchanged.

Progress snapshot:
- Shared UI macros introduced for page headers, help panels, and standardized file-picker controls.
- Shared theme spacing and card styling tightened for compact, consistent visual density.
- Beginner-help support expanded for file-input empty states and tailored hints.
- Additional top-level pages migrated to shared header macros.
- Standardized file-management and environment upload control wrappers.

Next action:
- Complete remaining page migrations to shared components and run focused wiring checks for UI-state regressions.

## Up Next

### Priority 2 - Export anonymization: participant ID renaming

Goal: fully anonymize participant identities in exported datasets while keeping source datasets untouched.

Scope:

| Step | What | Files affected |
|---|---|---|
| 1 | Rename sub-XXX -> sub-RNDXXX in folder/file names | sub-* directories and files |
| 2 | Replace participant IDs in TSV columns (participant_id, subject_id) | participants.tsv and sidecar TSV files |
| 3 | Replace participant IDs in JSON string values (IntendedFor, path references) | JSON sidecars across dataset |
| 4 | Save reversible mapping file outside shared export zip | code/anonymization_map.json |

Planned implementation targets:
- src/anonymizer.py
  - update_intendedfor_paths(json_data: dict, participant_mapping: dict) -> dict
- app/src/web/export_project.py
  - apply JSON path replacement when anonymize=true
- Keep UI and blueprint request flags unchanged (existing anonymize checkbox is sufficient).

Definition of done:
- Name/path/TSV/JSON replacements are all consistent in exported copy.
- IntendedFor supports both legacy and bids:: URI styles.
- Mapping file is generated and not shipped in public zip.
- Existing BIDS app compatibility remains intact.

## Deferred

### Priority 3 - JSON tag stripping and NIfTI GZIP header cleaning

Deferred until Priority 2 is merged.

Deferred scope summary:
- Strip identifying BIDS JSON tags from sidecars during export.
- Clean nii.gz GZIP header metadata fields (FNAME, MTIME) in exported copies.
- Add optional structural defacing integration gated by tool availability.

## Done (One-Line Summary)

Historical implementation detail now belongs in CHANGELOG.md and focused docs.

- 1.34: Added RTK wrapper command for setup, app runs, test and repo workflows.
- 1.33: Improved survey preview diagnostics and compact version selection UI.
- 1.32: Restored sourcedata quick-select across converter tabs with modality-aware filtering.
- 1.31: Added backend-owned survey preview review and selected-task conversion contract.
- 1.30: Mirrored dataset metadata into project.json and surfaced sync drift warnings.
- 1.29: Added detection for manual CITATION.cff drift against PRISM-managed metadata.
- 1.28: Added server file picker parity in File Management cards.
- 1.27: Added explicit server-connected picker mode setting.
- 1.25: Hardened converter modality tabs against stale source and project state reuse.
- 1.24: Bound converter helper state to visible project context.
- 1.23: Prevented Validator from posting stale default library overrides.
- 1.22: Updated PRISM App Runner route to render disabled HTML state instead of raw JSON.
- 1.21: Hardened Analysis Outputs against stale project and stale async run state.
- 1.20: Reset Recipe Builder correctly on project changes and blocked orphan saves.
- 1.19: Bound Survey Customizer save-to-project to loaded and active project context.
- 1.18: Bound Survey Export library state to visible project context.
- 1.17: Made Specifications quick links react to project changes.
- 1.16: Fixed JSON Editor project-root normalization and API fallback behavior.
- 1.15a: Hardened File Management wide-to-long save to target active project.
- 1.14: Bound File Management project copy actions to visible project.
- 1.13: Added Template Editor rollback for cancelled/failed source changes.
- 1.12: Refreshed Template Editor schema-aware validation badges on schema switch.
- 1.11: Bound Template Editor save/delete/list actions to visible project.
- 1.10: Stabilized Template Editor import/delete state transitions.
- 1.9: Bound metadata and methods actions to visible project.
- 1.8: Bound export preferences to explicit active project context.
- 1.7: Hardened async export cancellation and zip cleanup semantics.
- 1.6: Added overlap-safe participant ID anonymization for export paths and JSON refs.
- 1.5: Added safe participants merge workflow with preview and conflict blocking.
- 1.15b: Added survey Excel import multi-version support.
- 1.0: Added init-on-existing-BIDS workflow without overwriting existing files.
