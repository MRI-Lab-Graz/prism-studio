# PRISM Studio - Roadmap

Last updated: 2026-05-27

## Current Mission

Start the Read the Docs rewrite as a user-first documentation program while
keeping the existing frontend and backend guardrails green.
Focus on clearer public information architecture, deeper workflow docs with
examples, and visible DataLad guidance without changing product behavior.

## Status Board

| Priority | Title | Status | Next Action |
|---|---|---|---|
| 1.39 | Repository assessment remediation | IN PROGRESS | Continue the prioritized assessment queue with canonical-backend consolidation and focused regression guards after the completed low-risk fixes |
| 1.38 | Read the Docs rewrite: user-first information architecture and examples | IN PROGRESS | Complete the docs landing-page rewrite, establish public DataLad guidance, and validate the new navigation with a warnings-as-errors Sphinx build |
| 1.26 | UI harmonization and beginner-help improvements | COMPLETED | Keep shared-help-panel coverage and wiring regressions in standard frontend gates |
| 1.36 | Frontend structural assessment (page-by-page) | COMPLETED | Keep remediated workflow wiring and phase-boundary coverage confirmation in standard gates |
| 1.35 | Survey converter workflow hardening and backend command consolidation | COMPLETED | Keep post-merge stability checks in standard gates |
| 1.37 | DataLad mutation centralization and per-subject provenance runs | COMPLETED | Keep grouped DataLad-run rewrite/copy/delete/deface suites in standard backend regression gates |
| 2 | Export anonymization: participant ID renaming | COMPLETED | Keep export anonymization checks in standard gates |
| 3 | JSON tag stripping and NIfTI GZIP header cleaning | IN PROGRESS | Continue export privacy hardening after slice A (MRI sidecar scrub + .nii.gz header cleanup) |

## Active Work

### Priority 1.39 - Repository assessment remediation

Goal: resolve the highest-value findings from the repository assessment with
small, verifiable backend-ownership and CI-hardening slices instead of a broad
rewrite.

Current checkpoint:
- Completed recommendation 1: `app/src/batch_convert.py` is now a thin shim over `src/batch_convert.py` instead of a second implementation.
- Completed recommendation 2: PR and push coverage runs now include `app/src`.
- Completed recommendation 3: `app/src/derivatives/apps_runner_compat.py` now uses the canonical loader instead of `exec(compile(...), globals())`.
- Completed recommendation 4: `PrismValidator.spec` now includes the backend bundle and mirrors the optional-package excludes used by `PrismStudio.spec`.
- Completed recommendation 5: duplicated backend BIDS entity parsing now lives in the canonical `src/bids_entity_parser.py` helper and is reused by the rewrite/delete runners.
- Recommendation 6 is in progress: `src/recipes_surveys.py` shrank from 3696 LOC to ~2680 LOC by extracting three sub-modules — `src/recipes_formula_engine.py` (formula AST + scoring), `src/recipes_path_utils.py` (filename / participant-ID utilities), and `src/recipes_export_helpers.py` (SPSS / SAV / codebook helpers) — while preserving the existing import surface via re-exports. Remaining inside the file: aggregation/orchestration (`compute_survey_recipes`, `_export_recipe_*`, `_load_*`) and dataset-description/boilerplate generation.
- Completed recommendation 7: the main CI test-bearing workflow now runs coverage on Python 3.10 and 3.11, with a guard test to prevent matrix regression.
- Recommendation 8 was rechecked and found to be already satisfied by `.gitignore`; no code change was needed there.
- Completed recommendation 9: the DeepL translation helper note now lives under `docs/` instead of the repo root.
- Completed recommendation 10: a minimal Vitest harness now covers `app/static/js/shared/` helpers, starting with `validation.js`.
- Mainline CI now also includes a warnings-as-errors Sphinx docs build job.
- Focused regression coverage is in place for the batch-convert shim, compat-loader behavior, validator packaging guards, CI workflow matrix contract, the shared BIDS entity parser extraction, the first recipes formula-engine split, and the new shared-helper JS test harness.

Immediate next actions:
1. Continue recommendation 6 by extracting the next coherent `recipes_surveys` slice — most likely `_export_recipe_aggregated` / `_export_recipe_legacy` and the surrounding `_find_tsv_files` / `_load_participants_data` aggregation cluster — into a dedicated `src/recipes_survey_aggregation.py` module.
2. Expand the Vitest harness beyond `validation.js` into the next reusable shared helper modules (`storage.js`, `api.js`, or `job-polling.js`).
3. Keep using focused contract tests for each remaining assessment slice instead of broad speculative refactors.

### Priority 1.38 - Read the Docs rewrite: user-first information architecture and examples

Goal: rebuild the public documentation around clear learner paths, deep workflow
guides, and reusable worked examples while keeping the docs aligned with the
real backend-owned feature surface.

Current checkpoint:
- Landing information architecture rewrite is complete for the first public slice.
- The docs root is now organized around Fundamentals, Getting Started, User Workflows, Examples, CLI and Automation, Reference, and Integrations and Advanced.
- Core overview pages now separate PRISM the model from PRISM Studio the software and map the actual repo feature surface.
- A public DataLad page is now part of the visible docs because DataLad behavior materially affects real project setup and export usage.
- Projects, Converter, and Validator now have deeper task-oriented workflow pages instead of short placeholder summaries.
- Examples and Workshop now serve as a real examples layer for short success paths and longer onboarding paths.
- Warnings-as-errors Sphinx validation is green after the first rewrite slice.

Immediate next actions:
1. Continue with deep workflow rewrites for survey import, tools, template editing, recipe builder, and analysis outputs.
2. Reduce remaining duplication between overview pages and older detailed pages.
3. Add more downloadable example references and decision-support content where workflows still rely on jargon.
4. Keep validating each slice with a warnings-as-errors Sphinx build.

Maintenance action:
1. Keep documentation validation in standard release checks once the new navigation stabilizes.

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
- Validator phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_VALIDATOR_2026-05.md](docs/FRONTEND_ASSESSMENT_VALIDATOR_2026-05.md).
- Results phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_RESULTS_2026-05.md](docs/FRONTEND_ASSESSMENT_RESULTS_2026-05.md).
- Template Editor phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_TEMPLATE_EDITOR_2026-05.md](docs/FRONTEND_ASSESSMENT_TEMPLATE_EDITOR_2026-05.md).
- Recipe Builder phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_RECIPE_BUILDER_2026-05.md](docs/FRONTEND_ASSESSMENT_RECIPE_BUILDER_2026-05.md).
- Survey Customizer phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_SURVEY_CUSTOMIZER_2026-05.md](docs/FRONTEND_ASSESSMENT_SURVEY_CUSTOMIZER_2026-05.md).
- Survey Generator phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_SURVEY_GENERATOR_2026-05.md](docs/FRONTEND_ASSESSMENT_SURVEY_GENERATOR_2026-05.md).
- File Management phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_FILE_MANAGEMENT_2026-05.md](docs/FRONTEND_ASSESSMENT_FILE_MANAGEMENT_2026-05.md).
- JSON Editor phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_JSON_EDITOR_2026-05.md](docs/FRONTEND_ASSESSMENT_JSON_EDITOR_2026-05.md).
- Neurobagel workflow phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_NEUROBAGEL_WORKFLOW_2026-05.md](docs/FRONTEND_ASSESSMENT_NEUROBAGEL_WORKFLOW_2026-05.md).
- Library and Library Editor phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_LIBRARY_EDITOR_2026-05.md](docs/FRONTEND_ASSESSMENT_LIBRARY_EDITOR_2026-05.md).
- Specifications phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_SPECIFICATIONS_2026-05.md](docs/FRONTEND_ASSESSMENT_SPECIFICATIONS_2026-05.md).
- PRISM App Runner phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_PRISM_APP_RUNNER_2026-05.md](docs/FRONTEND_ASSESSMENT_PRISM_APP_RUNNER_2026-05.md).
- Home page phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_HOME_2026-05.md](docs/FRONTEND_ASSESSMENT_HOME_2026-05.md).
- Shared module phase checkpoint is captured in [docs/FRONTEND_ASSESSMENT_SHARED_MODULES_2026-05.md](docs/FRONTEND_ASSESSMENT_SHARED_MODULES_2026-05.md).
- Phase-boundary smoke sweep is complete (54 passed across the completed checkpoint suites).
- Initial remediation stabilization set is complete: Neurobagel fetch ownership unification, Library Editor module extraction with shared fallback save wiring, and PRISM App Runner stale-control cleanup.
- Library Editor advanced-mode CDN resilience slice is complete via explicit graceful-degrade behavior and focused wiring coverage.
- PRISM App Runner disabled-state contract hardening slice is complete with explicit frontend action guards and disabled-startup suppression.
- Shared-module API/project-state/polling contract coverage hardening slice is complete with focused wiring regression tests.
- Validator/Results abortable polling lifecycle hardening slice is complete with signal-aware single-loop guardrails and focused regression coverage.
- Validator target/request assembly consolidation slice is complete with shared request-option helpers across start paths.
- Results action-state contract hardening slice is complete with logic-level interaction guards.
- Focused cross-page smoke confirmation is complete (33 passed across remediated workflow suites).
- Phase-boundary full-suite coverage confirmation is complete (`./rtk coverage`: 2206 passed, 3 skipped).
- Coverage blocker remediation is complete: recipe merge-all score-prefix policy, participant-column export propagation, and SAV participant metadata/measure handling were repaired in backend recipe export logic.
- Detailed assessment plan remains in [docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md](docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md).

Closeout:
- Priority 1.36 high-risk remediation tranche is closed.
- Phase-boundary full-suite coverage confirmation is green.

Maintenance action:
1. Keep the focused cross-page remediation smoke suite and `./rtk coverage` in standard frontend release gates.

### Priority 1.35 - Survey converter workflow hardening and backend command consolidation

Status: completed and merged.

Reference:
- [docs/_archive/SURVEY_WORKFLOW_HARDENING_2026.md](docs/_archive/SURVEY_WORKFLOW_HARDENING_2026.md)

### Priority 1.37 - DataLad mutation centralization and per-subject provenance runs

Status: completed and merged.

Current checkpoint:
- Tracked mutation policy is centralized in `src/datalad_mutation_policy.py` and shared by rewrite/copy/delete/deface mutation flows.
- Converter project-save routes now delegate tracked copies through the canonical backend helper (`src/datalad_project_copy.py`) with strict missing-DataLad error behavior.
- OpenNeuro/DataLad defacing now preserves lazy materialization by resolving annex content only at deface execution time.
- Tracked mutation workflows (`copy`, `delete`, `deface`, `subject rewrite`, `entity rewrite`) now execute grouped `datalad run` commits per subject when applicable.
- Focused and broad regression slices are green after rollout (`77 passed` rewrite/policy/deleter/scrubber suite, `155 passed` conversion/contracts suite).

Maintenance action:
1. Keep grouped-run rewrite tests and conversion contract suites in standard backend release gates.

### Priority 3 - JSON tag stripping and NIfTI GZIP header cleaning

Goal: remove export-time metadata leakage from MRI sidecars and compressed NIfTI headers while preserving dataset usability.

Current checkpoint:
- Slice A completed in backend export pipeline: optional MRI sidecar sensitive-field scrubbing plus .nii.gz GZIP header normalization (mtime/FNAME).
- Route wiring updated so export privacy option (`scrub_mri_json`) enables both sidecar scrubbing and NIfTI header cleanup.
- Focused validation expanded (26 passed across export backend and blueprint contract suites), including root-level `.nii.gz` and cleaning-disabled header-preservation cases.
- Additional Priority 3 coverage slice completed: mixed-modality MRI sidecar scrubbing checks plus nested/derivative long-path `.nii.gz` header-cleaning checks.
- Focused export privacy suite is green after the expansion (`tests/test_projects_export_mapping_exclusion.py`: 15 passed).
- Defacing warning-only metadata is now surfaced in async export status payloads (non-blocking) and rendered in export success UI when risk is detected.
- Export submit UX now adds an explicit pre-export confirmation step when MRI scrub mode is enabled and defacing risk is detected.
- Export preferences now support configurable defacing confirmation mode (always ask vs ask only on detected risk), persisted per project in UI preferences.
- Backend app settings now provide a team-level default for export defacing confirmation mode, and export preference reads inherit this default when project preference is unset.
- Global Settings UI now exposes the backend export defacing confirmation default (risk vs always) and persists it through the settings API.
- Export card preference snapshot now shows defacing confirmation mode and indicates whether it is inherited from global settings or explicitly saved in project export preferences.
- Export UI now includes a one-click reset action that removes project defacing confirmation override and reverts behavior to inherited global default.
- Full defacing confirmation lifecycle coverage is now in place across the public settings and project export-preferences APIs (global default -> project override -> reset to inherited).
- Export defacing action is now mode-aware and non-mutating: both modes deface an export target copy; DataLad-preserving mode prepares a DataLad clone copy and runs pydeface via DataLad there, while DataLad-free mode defaces a plain structural copy.
- Export defacing now honors current export scope filters for subjects/sessions, so single-subject exports only run pydeface for that selected subset on the export copy.

Next action:
1. Keep the export privacy integration slice and adjacent settings/export API tests in standard release gates.

## Up Next

### Priority 2 - Export anonymization: participant ID renaming

Goal: fully anonymize participant identities in exported datasets while keeping source datasets untouched.

Execution note:
- [docs/_archive/PRIORITY_2_EXPORT_ANONYMIZATION_2026-05.md](docs/_archive/PRIORITY_2_EXPORT_ANONYMIZATION_2026-05.md)

Immediate next actions:
1. Completed: deterministic participant mapping wiring in project export adapters (sync + async routes).
2. Completed: TSV subject_id replacement and recursive JSON string-path rewrite integration checks (legacy + bids:: URI variants).
3. Completed: UI/API export smoke checks for async status rendering, anonymized filename generation, and status-payload hygiene.

Closeout:
- Priority 2 is complete and validated.
- Keep Priority 1.36 maintenance gates active.

## Deferred

No active deferred priorities.

## Done (Summary)

Historical completion entries were moved to:
- [docs/ROADMAP_HISTORY_2026.md](docs/ROADMAP_HISTORY_2026.md)

Changelog remains canonical for release-facing history:
- [CHANGELOG.md](CHANGELOG.md)

## Lessons Learned

- Mirrored `app/src` modules should not keep a full local implementation underneath a late canonical re-export; replace the file with a true shim or drift becomes invisible until runtime.
- Workflow-only fixes should get a small file-content guard test when possible; otherwise CI regressions can silently revert after unrelated YAML edits.
- When multiple backend maintenance tools share the same BIDS token and subject/session regex rules, promote those rules into one canonical parser helper before changing behavior in any one caller.
- Large backend module splits are safer when the new module preserves the old import surface first; keep `recipes_surveys.py` re-exporting extracted helpers until the surrounding tests no longer rely on those names.

- For Sphinx plus MyST docs in this repo, hidden Markdown pages must either live in a toctree or carry explicit `orphan: true` front matter, otherwise warnings-as-errors will block the build.
- The docs rewrite is easier to keep accurate when each page is treated as one of four types: concept, workflow, example, or reference.
- Keep icon assignment in backend metadata (project.json) and only render in frontend adapters to avoid drift between session, recent-project cache, and persisted project state.
- Export privacy tests should always include both positive MRI scrubbing assertions and non-MRI preservation checks, plus nested/derivative path variants for `.nii.gz` header cleaning.
- For potentially disruptive privacy checks, shipping warning metadata in async status first is a low-risk way to add guidance without blocking export flows.
- Adding a lightweight confirmation at submit-time is an effective second step to increase user awareness without introducing backend export blockers.
- Persisting the confirmation mode as project preference keeps privacy UX configurable without duplicating backend export logic.
- A backend default policy with project-level override provides a stable global baseline while preserving per-project flexibility.
- Exposing the global policy in Settings keeps team defaults discoverable while preserving project-level opt-in overrides.
- Showing source attribution (project override vs inherited default) in the export snapshot helps avoid ambiguity in privacy confirmation behavior.
- Supporting explicit reset-to-inherited in UI reduces misconfiguration risk and keeps global privacy policy enforcement easy to recover.
- When a policy is split across global settings and project preferences, keep one integration test that spans both public APIs; unit tests on each side are not enough to catch inheritance regressions.
- For export privacy tooling, keep source rawdata immutable in all export modes: route defacing to an export copy and, when provenance is needed, run pydeface via DataLad on a DataLad-preserving clone target.
- When export-side processing is user-triggered before export start, always apply the active export scope filters to avoid touching unselected subjects in the temporary/export copy workspace.
- Subject-grouped DataLad commits require subject-filter support in canonical rewrite engines; orchestration-only grouping is insufficient.
- Aggregated grouped-run API payloads should keep legacy top-level keys stable while attaching group provenance under a dedicated `datalad.groups` field.
