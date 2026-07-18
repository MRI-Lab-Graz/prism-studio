---
orphan: true
---

# Roadmap History 2026

Archived detail for completed roadmap priorities, trimmed from `ROADMAP.md`
to keep the active roadmap short. Full context also lives in git history
and the CHANGELOG.

## Priority 1.26 - UI harmonization and beginner-help improvements

Status: COMPLETED.

Goal: unify page-shell and file-input UX while preserving PRISM branding and keeping backend behavior unchanged.

Progress:
- Shared UI macros introduced for page headers, help panels, and standardized file-picker controls.
- Shared theme spacing and card styling tightened for compact, consistent visual density.
- Beginner-help support expanded for file-input empty states and tailored hints.
- Additional top-level pages migrated to shared header macros.
- Standardized file-management and environment upload control wrappers.
- Library editor, Validation Results, Projects, Home, JSON Editor, Template Editor, Survey Customizer, File Management, Recipe Builder, Specifications, Analysis Outputs, Validator main, Converter, and Survey Library pages all migrated to shared page-header + help-panel primitives, each with dedicated workflow wiring regression coverage.
- Added a top-level template coverage guard test to keep shared help-panel imports from regressing.
- Reconciled stale workflow-wiring assertions to current frontend module ownership (projects selection/open/bootstrap and converter log-renderer), with broad regression sweep passing.
- Library page action handlers extracted from inline template JS into a dedicated module using shared relative-path API fallback wiring.
- Project identity icons are now assigned per study via backend metadata, and rendered in navbar/current-project + recent-project surfaces with regression coverage.

Closeout:
- Top-level frontend shells now consistently use shared page-header/help-panel primitives.
- Library actions moved to a dedicated JS module with shared relative-path API fallback.
- Broad frontend gate is green (workflow wiring + shared help-panel coverage + template rendering + web formatting checks).

Maintenance action: keep the shared help-panel template coverage guard and broad frontend regression gate in standard validation runs.

## Priority 1.36 - Frontend structural assessment (page-by-page)

Status: COMPLETED.

Goal: assess each frontend page sequentially for workflow logic, hostile-usage resilience, stability, and execution speed.

Per-page checkpoints (all completed): Converter, Projects, Validator, Results,
Template Editor, Recipe Builder, Survey Customizer, Survey Generator, File
Management, JSON Editor, Neurobagel workflow, Library/Library Editor,
Specifications, PRISM App Runner, Home, Shared modules — each documented in
its own `docs/FRONTEND_ASSESSMENT_<PAGE>_2026-05.md` checkpoint file.

- Phase-boundary smoke sweep complete (54 passed across completed checkpoint suites).
- Initial remediation stabilization set complete: Neurobagel fetch ownership unification, Library Editor module extraction with shared fallback save wiring, PRISM App Runner stale-control cleanup.
- Library Editor advanced-mode CDN resilience slice complete via explicit graceful-degrade behavior and focused wiring coverage.
- PRISM App Runner disabled-state contract hardening slice complete with explicit frontend action guards and disabled-startup suppression.
- Shared-module API/project-state/polling contract coverage hardening slice complete with focused wiring regression tests.
- Validator/Results abortable polling lifecycle hardening slice complete with signal-aware single-loop guardrails and focused regression coverage.
- Validator target/request assembly consolidation slice complete with shared request-option helpers across start paths.
- Results action-state contract hardening slice complete with logic-level interaction guards.
- Focused cross-page smoke confirmation complete (33 passed across remediated workflow suites).
- Phase-boundary full-suite coverage confirmation complete (`./rtk coverage`: 2206 passed, 3 skipped).
- Coverage blocker remediation complete: recipe merge-all score-prefix policy, participant-column export propagation, and SAV participant metadata/measure handling repaired in backend recipe export logic.
- Detailed assessment plan previously lived at `docs/FRONTEND_STRUCTURAL_ASSESSMENT_2026-05.md`; removed as obsolete once this checkpoint was complete (see commit `71ebb706`).

Closeout: high-risk remediation tranche closed; phase-boundary full-suite coverage confirmation green.

Maintenance action: keep the focused cross-page remediation smoke suite and `./rtk coverage` in standard frontend release gates.

## Priority 1.35 - Survey converter workflow hardening and backend command consolidation

Status: completed and merged.

Reference: `docs/_archive/SURVEY_WORKFLOW_HARDENING_2026.md` (excluded from the
public docs build; browse it directly in the repo)

## Priority 1.37 - DataLad mutation centralization and per-subject provenance runs

Status: completed and merged. Remaining provenance gap (recipe scoring does
not yet run under `datalad run` and derivative metadata lacks input hashes)
is absorbed into Strategic Phase 2 of `ROADMAP.md`.

Checkpoint:
- Tracked mutation policy centralized in `src/datalad_mutation_policy.py` and shared by rewrite/copy/delete/deface mutation flows.
- Converter project-save routes delegate tracked copies through the canonical backend helper (`src/datalad_project_copy.py`) with strict missing-DataLad error behavior.
- OpenNeuro/DataLad defacing preserves lazy materialization by resolving annex content only at deface execution time.
- Tracked mutation workflows (`copy`, `delete`, `deface`, `subject rewrite`, `entity rewrite`) execute grouped `datalad run` commits per subject when applicable.
- Focused and broad regression slices green after rollout (77 passed rewrite/policy/deleter/scrubber suite, 155 passed conversion/contracts suite).

Maintenance action: keep grouped-run rewrite tests and conversion contract suites in standard backend release gates.

## Priority 2 - Export anonymization: participant ID renaming

Status: complete and validated.

Goal: fully anonymize participant identities in exported datasets while keeping source datasets untouched.

Reference: `docs/_archive/PRIORITY_2_EXPORT_ANONYMIZATION_2026-05.md` (excluded
from the public docs build; browse it directly in the repo)

Completed:
1. Deterministic participant mapping wiring in project export adapters (sync + async routes).
2. TSV subject_id replacement and recursive JSON string-path rewrite integration checks (legacy + `bids::` URI variants).
3. UI/API export smoke checks for async status rendering, anonymized filename generation, and status-payload hygiene.

Maintenance action: keep Priority 1.36 maintenance gates active.

## Strategic Phase 0 — Ship pending work (v1.16.0)

Landed native-window work and security hardening from
`feature/pywebview-native-window` on `main`:

- Security hardening: per-launch session secret, DNS-rebinding Host-header guard, loopback-only filesystem browse endpoints, `/editor` prefix fix, crash exit codes via excepthook, force-kill warning.
- CI change: lint/ruff/mypy job now runs on push/PR (`.github/workflows/ci.yml`).
- `[1.16.0]` CHANGELOG entry for native window + security fixes.
- Version markers bumped (`app/src/__init__.py`, `src/__init__.py`, `setup.py`, `CITATION.cff`, `codemeta.json`, `docs/conf.py`); `docs/RELEASE_NOTES_v1.16.0.md` written from template.
- PR opened and merged to main ([#77](https://github.com/MRI-Lab-Graz/prism-studio/pull/77)).

## Strategic Phase 1 — BIDS `phenotype/` bridge (v1.17)

Deliberately lossy compatibility bridge to vanilla BIDS `phenotype/`, not a
first-class conversion path — PRISM's per-session `survey/` layout stays
primary. Scope narrowed from the original plan during implementation (see
[PR #78](https://github.com/MRI-Lab-Graz/prism-studio/pull/78), merged to `main`):

- Export: aggregate `sub-*/ses-*/survey/*_survey.tsv` grouped by (TaskName, VariantID) → `phenotype/<name>.tsv` + flat column-keyed JSON sidecar; opt-in flag (`export_phenotype_bridge`) in all four existing export routes (sync/async ZIP, folder, Git LFS) — not a new export mode (`src/converters/phenotype_export.py`).
- Import: parse `phenotype/*.tsv` → PRISM `survey/` layout with a minimal, honest sidecar (no fuzzy-matching against `official/library/survey/` — deliberately out of scope); fires automatically (no confirmation prompt) when a project is initialized from an existing BIDS dataset containing `phenotype/`, with a post-hoc non-blocking banner (`src/converters/phenotype_import.py`, `app/src/project_manager.py`).
- Not wired into the Converter page or `conversion_survey_*` blueprints — kept visibly separate from PRISM's native survey conversion paths by design.
- Round-trip regression test asserting data fidelity and explicit metadata loss (`tests/test_phenotype_roundtrip.py`).

Done when: merged to `main` and exercised end-to-end against the
wellbeing-multi-demo example (done — PR #78). Formal BEP engagement
remains open-ended, not a release blocker (tracked in `ROADMAP.md` Phase 1).

## Strategic Phase 3 — Declarative entity/filename rules (v1.19)

Filename/entity rules expressed as data (`app/schemas/stable/entities.schema.json`
— datatypes, suffixes, allowed/required entities, entity ordering):

- `validator`/rewriter/fix-hints/modality-inference consume the rules file via `src/entity_rules.py`; hand-coded checks became data-driven for both the read path (`app/src/validator.py`, `src/bids_entity_rewriter.py`, `app/src/issues.py`, `app/src/fixer.py` — PR #81) and the write path (filename construction in `app/src/converters/survey_core.py`, `src/converters/biometrics.py`, `app/src/cli/commands/convert.py` — PR #82).
- Versioned with the existing schema channels: lives in `app/schemas/stable/`, loads through `schema_manager.load_schema()`'s normal version-aware path resolution. Deliberately not added to `schema_manager.py`'s `load_all_schemas()` modality registry — that list feeds `jsonschema.validate()` against sidecar content, and `entities.schema.json` isn't a JSON-Schema document, so mixing it in would be a category error.

Done when: adding a new suffix or entity requires only a rules-file edit
plus tests — no parser code changes (true for both validating and writing
filenames as of PRs #81/#82).

## Priority 3 - JSON tag stripping and NIfTI GZIP header cleaning

Status: COMPLETED.

Goal: remove export-time metadata leakage from MRI sidecars and compressed NIfTI headers while preserving dataset usability.

Checkpoint:
- Slice A completed in backend export pipeline: optional MRI sidecar sensitive-field scrubbing plus .nii.gz GZIP header normalization (mtime/FNAME).
- Route wiring updated so export privacy option (`scrub_mri_json`) enables both sidecar scrubbing and NIfTI header cleanup.
- Focused validation expanded (26 passed across export backend and blueprint contract suites), including root-level `.nii.gz` and cleaning-disabled header-preservation cases.
- Additional coverage slice: mixed-modality MRI sidecar scrubbing checks plus nested/derivative long-path `.nii.gz` header-cleaning checks.
- Focused export privacy suite green after the expansion (`tests/test_projects_export_mapping_exclusion.py`: 15 passed).
- Defacing warning-only metadata surfaced in async export status payloads (non-blocking) and rendered in export success UI when risk is detected.
- Export submit UX adds an explicit pre-export confirmation step when MRI scrub mode is enabled and defacing risk is detected.
- Export preferences support configurable defacing confirmation mode (always ask vs ask only on detected risk), persisted per project in UI preferences.
- Backend app settings provide a team-level default for export defacing confirmation mode; export preference reads inherit this default when project preference is unset.
- Global Settings UI exposes the backend export defacing confirmation default (risk vs always) and persists it through the settings API.
- Export card preference snapshot shows defacing confirmation mode and indicates whether it is inherited from global settings or explicitly saved in project export preferences.
- Export UI includes a one-click reset action that removes project defacing confirmation override and reverts behavior to inherited global default.
- Export defacing action is mode-aware and non-mutating: both modes deface an export target copy; DataLad-preserving mode prepares a DataLad clone copy and runs pydeface via DataLad there, while DataLad-free mode defaces a plain structural copy.
- Export defacing honors current export scope filters for subjects/sessions, so single-subject exports only run pydeface for that selected subset on the export copy.
- The "not ready for public sharing" defacing-risk warning no longer depends on the unrelated `scrub_mri_json` flag - it fires whenever the export (honoring its own `exclude_subjects`/`exclude_sessions` scope) includes un-defaced anatomical scans, with wording stating the sharing implication explicitly (`app/src/web/blueprints/projects_export_blueprint.py:_build_export_defacing_warning`).
- Fixed a bug found while touching this area: the "Run pydeface for export copy now" button (`exportRunDefacing`) had a fully-wired click handler in `export.js` but the `<button>` element itself was missing from `export_section.html`, so the action was unreachable from the UI. Added the button plus a time-cost note (near the button and in its confirm dialog) warning that defacing can take a long time across many scans.
- Full defacing-confirmation-mode lifecycle (global default → project override → reset to inherited) across both the global settings API and export preferences API is covered end-to-end via real HTTP routes: `tests/test_projects_library_settings_api.py::test_export_defacing_confirmation_mode_lifecycle_across_global_and_project_apis` (landed 2026-05-27, commit `8f851fb5`).

Done when: export-time MRI sidecar/NIfTI metadata leakage is scrubbed on request, defacing stays an explicit export-only opt-in with clear time-cost and non-sharing-readiness warnings, and the confirmation-mode preference lifecycle is regression-tested end-to-end — true today.
