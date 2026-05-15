# PRISM Studio - Roadmap

Last updated: 2026-05-15

## Current Mission

Continue Priority 1.36 execution as the primary workstream.
Focus on page-by-page structural assessment, runtime resilience checks, and focused smoke validation.

## Status Board

| Priority | Title | Status | Next Action |
|---|---|---|---|
| 1.26 | UI harmonization and beginner-help improvements | COMPLETED | Keep shared-help-panel coverage and wiring regressions in standard frontend gates |
| 1.36 | Frontend structural assessment (page-by-page) | IN PROGRESS | Execute Phase 1.2 Projects assessment and runtime smoke checks |
| 1.35 | Survey converter workflow hardening and backend command consolidation | COMPLETED | Keep post-merge stability checks in standard gates |
| 2 | Export anonymization: participant ID renaming | COMPLETED | Keep export anonymization checks in standard gates |
| 3 | JSON tag stripping and NIfTI GZIP header cleaning | DEFERRED | Revisit after Priority 2 is complete |

## Active Work

### Priority 1.26 - UI harmonization and beginner-help improvements

Goal: unify page-shell and file-input UX while preserving PRISM branding and keeping backend behavior unchanged.

Progress snapshot:
- Shared UI macros introduced for page headers, help panels, and standardized file-picker controls.
- Shared theme spacing and card styling tightened for compact, consistent visual density.
- Beginner-help support expanded for file-input empty states and tailored hints.
- Additional top-level pages migrated to shared header macros.
- Standardized file-management and environment upload control wrappers.
- Library editor page shell migrated to shared page header + help panel primitives, with focused wiring regression coverage.
- Validation results page header migrated to shared page-header primitive, with validator workflow wiring coverage.
- Projects page header migrated to shared page-header primitive while preserving preliminary badge behavior and compact-view wiring checks.
- Home page shell now uses shared page-header and help-panel primitives while preserving hero/content structure.
- JSON Editor now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- Template Editor now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- Survey Customizer now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- File Management page now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- Recipe Builder page now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- Specifications page now uses shared page-header and help-panel primitives, while preserving project-bound derivative link wiring checks.
- Analysis Outputs page now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- Validation Results page now uses shared page-header and help-panel primitives, with dedicated validator wiring assertions.
- Projects page now uses shared page-header and help-panel primitives, preserving preliminary badge visibility and beginner-help toggle behavior.
- Validator main page now uses shared page-header, section-card, and help-panel primitives, preserving validation target/progress wiring.
- Converter page now uses shared page-header and help-panel primitives, with dedicated converter workflow wiring assertions.
- Survey Library page now uses shared page-header and help-panel primitives, with dedicated workflow wiring assertions.
- Added a top-level template coverage guard test to keep shared help-panel imports from regressing.
- Reconciled stale workflow-wiring assertions to current frontend module ownership (projects selection/open/bootstrap and converter log-renderer), with broad regression sweep passing.
- Library page action handlers were extracted from inline template JS into a dedicated module using shared relative-path API fallback wiring.
- Project identity icons are now assigned per study via backend metadata, and rendered in navbar/current-project + recent-project surfaces with regression coverage.

Closeout:
- Top-level frontend shells now consistently use shared page-header/help-panel primitives.
- Library actions are moved to a dedicated JS module with shared relative-path API fallback.
- Broad frontend gate is green (workflow wiring + shared help-panel coverage + template rendering + web formatting checks).

Maintenance action:
1. Keep the shared help-panel template coverage guard and broad frontend regression gate in standard validation runs.

### Priority 1.36 - Frontend structural assessment (page-by-page)

Goal: assess each frontend page sequentially for workflow logic, hostile-usage resilience, stability, and execution speed.

Current checkpoint:
- Converter phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- Projects phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_PROJECTS_2026-05.md](docs/FRONTEND_ASSESSMENT_PROJECTS_2026-05.md).
- Detailed assessment plan remains in [docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md](docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md).

Next action:
- Continue phase sequence with Projects runtime resilience and state-transition verification, then Validator page assessment.

### Priority 1.35 - Survey converter workflow hardening and backend command consolidation

Status: completed and merged.

Reference:
- [docs/SURVEY_WORKFLOW_HARDENING_2026.md](docs/SURVEY_WORKFLOW_HARDENING_2026.md)

## Up Next

### Priority 2 - Export anonymization: participant ID renaming

Goal: fully anonymize participant identities in exported datasets while keeping source datasets untouched.

Execution note:
- [docs/PRIORITY_2_EXPORT_ANONYMIZATION_2026-05.md](docs/PRIORITY_2_EXPORT_ANONYMIZATION_2026-05.md)

Immediate next actions:
1. Completed: deterministic participant mapping wiring in project export adapters (sync + async routes).
2. Completed: TSV subject_id replacement and recursive JSON string-path rewrite integration checks (legacy + bids:: URI variants).
3. Completed: UI/API export smoke checks for async status rendering, anonymized filename generation, and status-payload hygiene.

Closeout:
- Priority 2 is complete and validated.
- Continue execution on Priority 1.36 active workstream.

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

## Lessons Learned

- Keep icon assignment in backend metadata (project.json) and only render in frontend adapters to avoid drift between session, recent-project cache, and persisted project state.
