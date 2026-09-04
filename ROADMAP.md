# PRISM Studio - Roadmap

Last updated: 2026-08-07

## Recent Checkpoints

- [x] 2026-09-04: Fixed standard BIDS validation on current Deno releases by
      enabling Deno's automatic Node-compatible module directory for the pinned
      `jsr:@bids/validator` dependency graph. Regression coverage verifies the
      launch contract. Lesson learned: upstream JSR CLIs may load npm packages
      through Node resolution and require `--node-modules-dir=auto` even when
      the top-level command is a JSR specifier.

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

### Phase 0 — Ship pending work (v1.16.0) — DONE

Native-window work and security hardening from `feature/pywebview-native-window`
landed on `main` via [PR #77](https://github.com/MRI-Lab-Graz/prism-studio/pull/77).

Note: `v1.16.0` tag was deliberately held — per-phase decision (2026-07-05),
the next git tag was to be cut only once Phases 1-5 were also complete,
bundling this work into that later release. Phases 1-5 are now all DONE
(2026-07-18) — the bundling condition is met; cutting/naming the actual next
release tag is a separate decision, not made here.

### Phase 1 — BIDS `phenotype/` bridge (v1.17) — DONE (merged, unreleased)

Deliberately lossy compatibility bridge to vanilla BIDS `phenotype/` (export
aggregation + automatic import on BIDS-dataset init), kept visibly separate
from PRISM's native survey conversion paths. Merged via
[PR #78](https://github.com/MRI-Lab-Graz/prism-studio/pull/78), round-trip
regression test in place.

Ongoing (not a release blocker): engage the BIDS phenotype BEP process; keep
`docs/BIDS_SURVEY_MODALITY_PR_DRAFT.md` aligned.

### Phase 2 — Recipe & derivative provenance (v1.18) — DONE (merged, unreleased)

Goal: make every computed derivative auditable. Extends completed Priority
1.37 (tracked mutations already run under grouped `datalad run`) to recipe
scoring.

- [x] Real `GeneratedBy` metadata (version from `src/__init__.py`) in
      derivative `dataset_description.json`
      (`_write_recipes_dataset_description`, `src/recipes_surveys.py:848-909`)
- [x] Provenance sidecar per recipe output: recipe id + version, input file
      list + SHA256 hashes, PRISM version, timestamp
      (`_write_recipe_provenance_sidecar`, `src/recipes_surveys.py:937-976`)
- [x] Landed in commit `e6c016f0` ("Add provenance to recipe-computed
      derivatives (Phase 2)", 2026-07-06)

Deliberately not done, not a gap: routing recipe scoring through
`run_datalad_run()` (`src/datalad_execution.py`). `compute_survey_recipes()`
uses a scoped `run_datalad_save()` instead
(`src/recipes_surveys.py:2777-2802`) — per the `e6c016f0` commit message,
`datalad run` requires a clean-working-tree precondition (fragile, already
documented elsewhere in this codebase) and would need scoring wrapped as a
`python -c` subprocess call (the only pattern `run_datalad_run()`/
`run_tracked_mutation()` support today, per `src/bids_file_deleter.py` and
`src/datalad_project_copy.py`). The structured provenance sidecar was judged
a better audit trail than a `datalad run` command-string record. Revisit only
if a concrete need for a `datalad run` commit (not just sidecar provenance)
surfaces.

Done when: a scored derivative can be traced to exact inputs and recipe
version from its sidecars alone — true today via the provenance sidecar.

### Phase 3 — Declarative entity/filename rules (v1.19) — DONE (merged, unreleased)

Filename/entity rules expressed as data (`app/schemas/stable/entities.schema.json`)
and consumed by validator/rewriter/fix-hints/modality-inference on both the
read path (PR #81) and write path (PR #82) via `src/entity_rules.py`.

Explicitly deferred, not silently dropped: `app/src/project_manager.py`'s
default-modality lists and `app/src/bids_integration.py`'s `.bidsignore`
generation still hardcode their own modality lists independently — left
alone given the DataLad text-file policy risk in `CLAUDE.md`. A handful of
UI-only datatype guards in `app/src/web/blueprints/*.py` were also out of
scope (they encode which modalities the Template Editor/Recipe Builder
*feature* supports, not filename grammar).

### Phase 4 — Instrument registry & variable semantics (v1.20) — DONE

Goal: make cross-study pooling trustworthy. Reuses the identity fields
already threaded through filenames/phenotype export — `Study.TaskName`
(falling back to the template filename) plus `Study.VariantDefinitions` —
rather than inventing a new ID scheme.

- [x] Central registry index over `official/library/survey/` (104
      instruments): stable TaskName + version + DOI + citation per entry,
      generated by `scripts/generate_instrument_registry.py` via
      `src/instrument_registry.py` into `official/library/survey/index.json`,
      shaped by `app/schemas/stable/instrument-registry.schema.json`
      (loaded directly by name, same precedent as `entities.schema.json` —
      not a sidecar-validation target)
- [x] Backfill `Study.Version`/`Study.DOI` in conversion output sidecars
      from the registry whenever the converted template didn't already
      carry them (`app/src/converters/survey_io.py:_write_task_sidecars`),
      falling back to the acq/variant slug when no single version is on
      file; fixed an adjacent hardcoded `GeneratedBy` version bug in
      `app/src/converters/survey.py:_write_survey_description` along the way
- [x] Optional `Vocabulary` field (NIH CDE/SNOMED/DOI URI) added to the
      registry schema — data field only, not populated by the generator and
      no Neurobagel annotation pipeline wired up; deliberately deferred
      until a concrete need surfaces (today's Neurobagel integration only
      annotates `participants.tsv` columns, not instrument identity)

Done when: two datasets converted from the same instrument are
machine-identifiable as such via sidecar metadata alone — true via the
registry-backed `Study.Version`/`Study.DOI` backfill.

### Phase 5 — Formal spec, scope tiers, CI action (v2.0) — DONE

Goal: give the PRISM format an existence independent of the app, and narrow
the supported product surface.

- [x] `docs/specs/entities.md` — first prose spec page for Phase 3's
      `entities.schema.json` (previously code-comment-only); `docs/SPECIFICATIONS.md`
      extended to link it plus the previously-omitted `project`/`recipe.survey`/
      `tool-limesurvey`/`dataset_description` schemas, and now carries a
      "Specification version" note tracking the `stable` schema version with
      a placeholder Zenodo-DOI mention (mirrors `paper/paper.md`'s own
      pending-DOI convention — neither DOI is minted yet)
- [x] Core loop | Supported | Experimental feature-tier table in
      `README.md`, seeded from scope decisions already recorded in this
      roadmap (Phases 1-4) plus the one genuinely-flagged unstable code path
      (`convert_varioport.py`'s Type-7 multiplexed decoder); docs only, no
      new UI badge mechanism
- [x] `action.yml` — one-step GitHub Action wrapping
      `ghcr.io/mri-lab-graz/prism-validator`; `official/anc_templates/example-github-actions.yml`
      updated to use it, and `example-gitlab-ci.yml`'s dead `PRISM_VERSION`
      variable (declared but never used to pin anything) replaced with a
      `PRISM_VALIDATOR_IMAGE_TAG` that actually pins the direct Docker
      invocation (GitLab CI can't consume a GitHub composite Action); both
      promoted from README's Docker-validator section

Done when: a third party can cite the spec, validate a dataset in CI with
one workflow line, and tell at a glance which features are core-supported —
true via `action.yml` + the README feature-tier table (Zenodo DOI itself
still pending, same as the JOSS paper's software DOI).

## Current Mission

All six strategic phases (0-5) and all tactical priorities are DONE — there
is no open roadmap item as of 2026-07-18. Focus is on sustaining the
standing regression gates accumulated across those phases (frontend
structural-assessment guardrails, `./rtk coverage`, grouped-run DataLad
tests, export anonymization/privacy/defacing suites) rather than new
feature work, until a new strategic initiative is picked.

## JOSS Publication Readiness

- [x] Verify that the manuscript's capability claims and bundled-template
      counts are supported by the v1.17.0 release.
- [x] Identify documented research use: the Austrian NeuroCloud dataset
      *Creativity: a (white) matter of connectivity*
      (DOI: `10.60817/sama-va10`) records PRISM Studio v1.15.2 as its creation
      tool.
- [x] Align the manuscript with v1.17.0, add the dataset citation, and replace
      the generic AI disclosure with the verified tool and responsibility
      statement.
- [x] Strengthen the design narrative around the template-to-sharing lifecycle,
      the loss-aware BIDS `phenotype/` bridge, standalone validator, derivative
      provenance, controlled sharing, and bounded FAIR-oriented support; add
      conceptual lifecycle and representation figures.
- [x] Reconcile `codemeta.json` with the earliest repository commit
      (`2025-09-09`) and the manuscript's public-development history.
- [x] Replace obsolete contributor test commands and add a private security
      reporting policy.
- [x] Validate the manuscript source with the official JOSS paper checker;
      keep generated PDF and JATS artifacts out of version control because
      Overleaf is the authoring environment.
- [x] Remove the tracked session-assignment audit report from all mutable
      branches and tags, ignore future `reports/` artifacts, and reject them in
      `tests/verify_repo.py`.
- [ ] Ask GitHub Support to purge the server-managed pull-request heads #65-71
      and #73-104, which retain the removed audit report and cannot be rewritten
      through Git; do not publish before the purge is confirmed.
- [ ] Archive the immutable v1.17.0 source snapshot after successful review,
      then add the resulting software DOI to citation metadata, README, and
      the final paper.

## Status Board (tactical execution layer)

No open tactical priorities. Priority 3 (JSON tag stripping and NIfTI GZIP
header cleaning) is now COMPLETED — its "next action" (full defacing
confirmation-mode lifecycle test across the global settings and export
preferences APIs) turned out to already exist and pass
(`tests/test_projects_library_settings_api.py::test_export_defacing_confirmation_mode_lifecycle_across_global_and_project_apis`,
landed 2026-05-27) — this roadmap just hadn't been updated to reflect it.

Completed priorities (1.26, 1.35, 1.36, 1.37, 2, 3) are archived in
[docs/ROADMAP_HISTORY_2026.md](docs/ROADMAP_HISTORY_2026.md); their standing
maintenance gates (shared help-panel coverage, `./rtk coverage`, grouped-run
rewrite tests, export anonymization checks, export privacy/defacing
regression suites) stay part of standard release validation.

## Active Work

Publication hygiene: obtain GitHub Support confirmation that the sensitive
audit report has been purged from immutable pull-request references before
making the repository public.

## Deferred

No active deferred priorities.

## Done (Summary)

Historical completion entries were moved to:
- [docs/ROADMAP_HISTORY_2026.md](docs/ROADMAP_HISTORY_2026.md)

Changelog remains canonical for release-facing history:
- [CHANGELOG.md](CHANGELOG.md)

## Lessons Learned

- A dataset DOI can demonstrate documented PRISM use, but it must remain
      distinct from the software archive DOI required for the final JOSS release.
- Research-impact claims should cite a public record and state the exact
      verified workflow without implying independent adoption or broader access.
- Removing a sensitive file from branches and tags is insufficient on GitHub:
      pull-request references can retain it and require a Support purge. Keep
      generated reports ignored and block them in the repository verifier.
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
