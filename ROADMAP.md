# PRISM Studio - Roadmap

Last updated: 2026-05-12

## Current Mission

Sequentially merge survey-workflow-hardening into main using a stacked PR flow.
This is the top delivery goal for the current cycle.

## Status Board

| Priority | Title | Status | Next Action |
|---|---|---|---|
| 1.36 | Frontend structural assessment (page-by-page) | IN PROGRESS | Complete Phase 1 converter assessment and create remediation slices |
| 1.35 | Survey converter workflow hardening and backend command consolidation | IN PROGRESS | Execute stacked PR merge sequence to main |
| 1.26 | UI harmonization and beginner-help improvements | IN PROGRESS | Finish remaining page migrations to shared UI primitives |
| 2 | Export anonymization: participant ID renaming | TODO | Implement JSON/TSV/path replacement pass in export flow |
| 3 | JSON tag stripping and NIfTI GZIP header cleaning | DEFERRED | Revisit after Priority 2 is complete |

## Active Work

### Priority 1.36 - Frontend structural assessment (page-by-page)

Goal: assess each frontend page sequentially for workflow logic, hostile-usage resilience, stability, and execution speed.

Non-negotiable rule:
- Frontend actions must execute as backend commands.
- Frontend should only prepare command payloads, guide user input, trigger backend execution, and render progress/results.
- Exception: Project page may keep limited frontend-heavy orchestration where backend-only usage is impractical.

Assessment framework:
- Template: [docs/FRONTEND_PAGE_ASSESSMENT_TEMPLATE.md](docs/FRONTEND_PAGE_ASSESSMENT_TEMPLATE.md)
- Program roadmap: [docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md](docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md)

Current step:
- Phase 1.1 Converter assessment in progress.
- Output includes severity-ranked findings and remediation slices with RTK-first validation.
- First artifact: [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md)
- Slice A complete for Environment/Physio/Eyetracking (abort-aware polling + project-change backend cancel dispatch).
- Slice B expanded to Environment/Physio/Eyetracking/Biometrics/Participants (duplicate-submit guard via shared run controller).
- Slice B now includes explicit participants preview/convert click-storm regression assertions.

Immediate execution slices:
- Slice A: polling cancellation + project-change stability
- Slice B: duplicate-submit and backend command ownership hardening
- Slice C: rendering safety/performance cleanup

Exit criteria for this priority:
- Every frontend page has an assessment report with command-ownership map.
- Critical and High findings are either fixed or explicitly deferred with rationale.
- Pre-release gate includes hostile-usage + stability checklist and RTK validation commands.

### Priority 1.35 - Survey converter workflow hardening and backend command consolidation

Goal: reduce survey converter complexity and finish safe merge to main via ordered stacked PRs.

Current checkpoint:
- Workflow path hardening + explicit project-path contracts are implemented and covered.
- Converter runtime compatibility bridge (`src._compat`) is implemented and covered.
- Focused RTK suites are green for converter workflow wiring and endpoint contracts.

Detailed tracking moved to:
- [docs/SURVEY_WORKFLOW_HARDENING_2026.md](docs/SURVEY_WORKFLOW_HARDENING_2026.md)

Immediate next actions:
1. Continue stacked merge sequence from the detailed playbook doc.
2. Keep RTK-first gates on each stacked branch (`./rtk test ...`, `./rtk coverage`).
3. Run post-merge verification on main before release tagging.

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

## Done (Summary)

Historical completion entries were moved to:
- [docs/ROADMAP_HISTORY_2026.md](docs/ROADMAP_HISTORY_2026.md)

Changelog remains canonical for release-facing history:
- [CHANGELOG.md](CHANGELOG.md)
