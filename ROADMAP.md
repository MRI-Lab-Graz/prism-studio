# PRISM Studio - Roadmap

Last updated: 2026-07-05

## Vision

PRISM brings BIDS discipline to the modalities BIDS forgot — surveys,
biometrics, environment, physio — and enforces it from collection time
onward. The instrument codebook is the single source of truth for the whole
loop: design instrument → collect (LimeSurvey) → convert → validate →
version (DataLad) → export/share. PRISM's per-session `survey/` layout stays
the primary format; standard BIDS remains a first-class import/export
target, never a fork we drift away from.

## Strategic Roadmap

Release-mapped phases. Each phase lists its goal, key work items, affected
areas, and an explicit done-when. The tactical board below this section
remains the day-to-day execution layer.

### Phase 0 — Ship pending work (v1.16.0, immediate)

Goal: land the native-window work and the security hardening from
`feature/pywebview-native-window` on `main` before starting strategic work.

- [x] Commit security hardening (per-launch session secret, DNS-rebinding
      Host-header guard, loopback-only filesystem browse endpoints,
      `/editor` prefix fix, crash exit codes via excepthook, force-kill
      warning)
- [x] Commit CI change: lint/ruff/mypy job now runs on push/PR
      (`.github/workflows/ci.yml`)
- [x] Add `[1.16.0]` CHANGELOG entry for native window + security fixes
- [x] Bump version markers (`app/src/__init__.py`, `src/__init__.py`,
      `setup.py`, `CITATION.cff`, `codemeta.json`, `docs/conf.py`), write
      `docs/RELEASE_NOTES_v1.16.0.md` from template
- [x] Open PR → main ([#77](https://github.com/MRI-Lab-Graz/prism-studio/pull/77))
- [ ] **Tag deliberately held**: `v1.16.0` will not be tagged/released on its
      own. Per-phase decision (2026-07-05): merges land on `main`
      incrementally, but the next git tag is cut only once Phases 1-5 are
      also complete, bundling this security/native-window work into that
      later release. Revisit if security-fix urgency changes.

Done when: PR #77 is merged to `main`. (Tag/release deferred — see note
above.)

### Phase 1 — BIDS `phenotype/` bridge (v1.17) — DONE (merged, unreleased)

Goal: a deliberately lossy compatibility bridge to vanilla BIDS
`phenotype/`, not a first-class conversion path — PRISM's per-session
`survey/` layout stays primary, and the bridge exists only so data isn't
silently stranded in either direction. Scope was narrowed from the original
plan during implementation (see PR #78, merged to `main`):

- [x] Export: aggregate `sub-*/ses-*/survey/*_survey.tsv` grouped by
      (TaskName, VariantID) → `phenotype/<name>.tsv` + flat column-keyed
      JSON sidecar; opt-in flag (`export_phenotype_bridge`) in all four
      existing export routes (sync/async ZIP, folder, Git LFS) — **not**
      a new export mode (`src/converters/phenotype_export.py`)
- [x] Import: parse `phenotype/*.tsv` → PRISM `survey/` layout with a
      minimal, honest sidecar (no fuzzy-matching against
      `official/library/survey/` — deliberately out of scope to keep
      engineering investment low); fires **automatically** (no
      confirmation prompt) when a project is initialized from an existing
      BIDS dataset containing `phenotype/`, with a post-hoc non-blocking
      banner (`src/converters/phenotype_import.py`,
      `app/src/project_manager.py`)
- [x] **Not** wired into the Converter page or `conversion_survey_*`
      blueprints — kept visibly separate from PRISM's native survey
      conversion paths by design
- [x] Round-trip regression test asserting data fidelity *and* explicit
      metadata loss (`tests/test_phenotype_roundtrip.py`)
- [ ] Ongoing: engage the BIDS phenotype BEP process; keep
      `docs/BIDS_SURVEY_MODALITY_PR_DRAFT.md` aligned

Done when: merged to `main` and exercised end-to-end against the
wellbeing-multi-demo example (done — see PR #78). Formal BEP engagement
remains open-ended, not a release blocker.

### Phase 2 — Recipe & derivative provenance (v1.18)

Goal: make every computed derivative auditable. Extends completed Priority
1.37 (tracked mutations already run under grouped `datalad run`) to recipe
scoring, which today writes a hardcoded `GeneratedBy.Version: "1.0.0"`, no
input hashes, and bypasses `datalad run`.

- [ ] Real `GeneratedBy` metadata (version from `src/__init__.py`) in
      derivative `dataset_description.json` (`src/recipes_surveys.py`,
      `src/recipes_export_helpers.py`)
- [ ] Provenance sidecar per recipe output: recipe id + version, input file
      list + hashes, PRISM version, timestamp
- [ ] Route recipe scoring through existing `run_datalad_run()`
      (`src/datalad_execution.py`) when the project is a DataLad dataset

Done when: a scored derivative can be traced to exact inputs and recipe
version from its sidecars alone, and DataLad projects show a `datalad run`
commit for scoring.

### Phase 3 — Declarative entity/filename rules (v1.19) — DONE (merged, unreleased)

Goal: express filename/entity rules as data, the way sidecar validation
already is (JSON Schema in `app/schemas/`). Entity conventions previously
lived only in code (`src/bids_entity_parser.py`, `src/bids_entity_rewriter.py`)
and prose. This is the prerequisite for third-party implementations and the
v2.0 spec.

- [x] Machine-readable rules file: `app/schemas/stable/entities.schema.json`
      — datatypes, suffixes, allowed/required entities, entity ordering
      (`.schema.json` extension to match every other file in
      `app/schemas/`, not the `.json` originally sketched here)
- [x] `validator`/rewriter/fix-hints/modality-inference consume the rules
      file via new `src/entity_rules.py`; hand-coded checks became
      data-driven for both the read path (`app/src/validator.py`,
      `src/bids_entity_rewriter.py`, `app/src/issues.py`,
      `app/src/fixer.py` — PR #81) and the write path (filename
      construction in `app/src/converters/survey_core.py`,
      `src/converters/biometrics.py`,
      `app/src/cli/commands/convert.py` — PR #82)
- [x] Versioned with the existing schema channels: lives in
      `app/schemas/stable/`, loads through `schema_manager.load_schema()`'s
      normal version-aware path resolution like every other schema file.
      Deliberately *not* added to `schema_manager.py`'s `load_all_schemas()`
      modality registry — that list feeds `jsonschema.validate()` against
      sidecar content, and `entities.schema.json` isn't a JSON-Schema
      document, so mixing it in would be a category error.

Done when: adding a new suffix or entity requires only a rules-file edit
plus tests — no parser code changes (true for both validating and writing
filenames as of PRs #81/#82).

Explicitly deferred, not silently dropped: `app/src/project_manager.py`'s
default-modality lists and `app/src/bids_integration.py`'s `.bidsignore`
generation still hardcode their own modality lists independently — left
alone given the DataLad text-file policy risk in `CLAUDE.md`. A handful of
UI-only datatype guards in `app/src/web/blueprints/*.py` were also out of
scope for the entity-rules work itself (they encode a different concept —
which modalities the Template Editor/Recipe Builder *feature* supports,
not filename grammar).

### Phase 4 — Instrument registry & variable semantics (v1.20)

Goal: make cross-study pooling trustworthy. Instrument files already carry
rich metadata (DOI, citation, version, i18n) — expose it as a registry with
stable IDs and stamp identity into converted data.

- [ ] Central registry index over `official/library/survey/` (105
      instruments): stable instrument ID + version + DOI per entry
- [ ] Stamp instrument ID/version into conversion output sidecars
- [ ] Optional external vocabulary URIs per item (NIH CDEs, SNOMED, or
      instrument DOIs); feeds Neurobagel annotations

Done when: two datasets converted from the same instrument are
machine-identifiable as such via sidecar metadata alone.

### Phase 5 — Formal spec, scope tiers, CI action (v2.0)

Goal: give the PRISM format an existence independent of the app, and narrow
the supported product surface.

- [ ] Unified, versioned "PRISM Specification" document assembled from
      `docs/specs/*`, the JSON Schemas, and the entity rules; Zenodo DOI per
      spec version (complements the JOSS paper in `paper/`)
- [ ] Scope-narrowing audit: feature-tier table (Core loop | Supported |
      Experimental) in README/docs; peripheral features labeled in the UI
- [ ] Package the existing Docker validator as a one-line GitHub Action
      (`action.yml` wrapping `ghcr.io/mri-lab-graz/prism-validator`);
      promote the downstream CI examples
      (`official/anc_templates/example-{github-actions,gitlab-ci}.yml`)
      into the docs

Done when: a third party can cite the spec, validate a dataset in CI with
one workflow line, and tell at a glance which features are core-supported.

## Current Mission

Sustain completed Priority 1.36 guardrails as the primary frontend baseline.
Focus on keeping structural assessment remediations, runtime resilience checks, and focused smoke/coverage gates green.

## Status Board (tactical execution layer)

| Priority | Title | Status | Next Action |
|---|---|---|---|
| 1.26 | UI harmonization and beginner-help improvements | COMPLETED | Keep shared-help-panel coverage and wiring regressions in standard frontend gates |
| 1.36 | Frontend structural assessment (page-by-page) | COMPLETED | Keep remediated workflow wiring and phase-boundary coverage confirmation in standard gates |
| 1.35 | Survey converter workflow hardening and backend command consolidation | COMPLETED | Keep post-merge stability checks in standard gates |
| 1.37 | DataLad mutation centralization and per-subject provenance runs | COMPLETED | Follow-up work continues as Strategic Phase 2 (recipe/derivative provenance) |
| 2 | Export anonymization: participant ID renaming | COMPLETED | Keep export anonymization checks in standard gates |
| 3 | JSON tag stripping and NIfTI GZIP header cleaning | IN PROGRESS | Continue export privacy hardening after slice A (MRI sidecar scrub + .nii.gz header cleanup) |

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

Status: completed and merged. Remaining provenance gap (recipe scoring does
not yet run under `datalad run` and derivative metadata lacks input hashes)
is absorbed into Strategic Phase 2 above.

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
- Export defacing action is now mode-aware and non-mutating: both modes deface an export target copy; DataLad-preserving mode prepares a DataLad clone copy and runs pydeface via DataLad there, while DataLad-free mode defaces a plain structural copy.
- Export defacing now honors current export scope filters for subjects/sessions, so single-subject exports only run pydeface for that selected subset on the export copy.

Next action:
1. Add an integration test that validates full defacing policy lifecycle (global default -> project override -> reset to inherited) across settings and export preferences APIs.

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

- Keep icon assignment in backend metadata (project.json) and only render in frontend adapters to avoid drift between session, recent-project cache, and persisted project state.
- Export privacy tests should always include both positive MRI scrubbing assertions and non-MRI preservation checks, plus nested/derivative path variants for `.nii.gz` header cleaning.
- For potentially disruptive privacy checks, shipping warning metadata in async status first is a low-risk way to add guidance without blocking export flows.
- Adding a lightweight confirmation at submit-time is an effective second step to increase user awareness without introducing backend export blockers.
- Persisting the confirmation mode as project preference keeps privacy UX configurable without duplicating backend export logic.
- A backend default policy with project-level override provides a stable global baseline while preserving per-project flexibility.
- Exposing the global policy in Settings keeps team defaults discoverable while preserving project-level opt-in overrides.
- Showing source attribution (project override vs inherited default) in the export snapshot helps avoid ambiguity in privacy confirmation behavior.
- Supporting explicit reset-to-inherited in UI reduces misconfiguration risk and keeps global privacy policy enforcement easy to recover.
- For export privacy tooling, keep source rawdata immutable in all export modes: route defacing to an export copy and, when provenance is needed, run pydeface via DataLad on a DataLad-preserving clone target.
- When export-side processing is user-triggered before export start, always apply the active export scope filters to avoid touching unselected subjects in the temporary/export copy workspace.
- Subject-grouped DataLad commits require subject-filter support in canonical rewrite engines; orchestration-only grouping is insufficient.
- Aggregated grouped-run API payloads should keep legacy top-level keys stable while attaching group provenance under a dedicated `datalad.groups` field.
