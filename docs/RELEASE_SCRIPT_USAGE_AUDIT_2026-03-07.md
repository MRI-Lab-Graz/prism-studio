# Release Script Usage Audit (2026-03-07)

## Scope
Determine which scripts are not used by the PRISM web interface runtime path.

Web runtime traced from:
- `prism-studio.py` -> `app/prism-studio.py`
- registered blueprints in `app/prism-studio.py`
- imports in `app/src/web/**`

## Key Findings
- The web app does not execute anything in `scripts/**` directly.
- Most `app/helpers/**` files are not web-runtime dependencies.
- One helper is web-critical: `app/helpers/physio/convert_varioport.py`.
- `app/src/maintenance/**` is not used by web directly, but is used by `prism_tools` CLI (`app/src/cli/commands/library.py`).
- `scripts/build/build_app.py` is used by release CI workflow and must stay.

## Backend-First Guardrail
- Frontend/web routes should orchestrate only; heavy data transformations must stay in backend modules.
- Archival decisions should prefer removing ad-hoc helper scripts before touching backend modules used by CLI or web blueprints.
- Any script that embeds core data logic should either:
  - move into `app/src/**` backend modules with tests, or
  - remain clearly marked as manual tooling outside web runtime.

## Evidence (high signal)
- Build workflow uses `scripts/build/build_app.py`:
  - `.github/workflows/build.yml:52`
- Web physio conversion imports helper directly:
  - `app/src/web/blueprints/conversion.py:70`
  - `app/src/web/blueprints/conversion_physio_handlers.py:27`
- Maintenance modules are used by CLI library commands:
  - `app/src/cli/commands/library.py:22`
  - `app/src/cli/commands/library.py:23`
  - `app/src/cli/commands/library.py:35`
  - `app/src/cli/commands/library.py:42`
- Global library setup scripts are user-documented:
  - `README.md:53`
- BIDS compliance script is documented for validation workflows:
  - `docs/QUICK_REFERENCE_BIDS.md:200`

## Classification Matrix

### Keep
- `scripts/build/build_app.py`
  - release pipeline dependency
- `app/helpers/physio/convert_varioport.py`
  - imported by web blueprints
- `app/src/maintenance/sync_biometrics_keys.py`
- `app/src/maintenance/sync_survey_keys.py`
- `app/src/maintenance/catalog_survey_library.py`
- `app/src/maintenance/fill_missing_metadata.py`
  - needed for `prism_tools library ...`
- `scripts/setup/configure_global_library.py`
- `scripts/setup/verify_global_library.py`
- `scripts/setup/show_global_config.py`
  - externally documented setup path
- `scripts/ci/test_bids_compliance.py`
  - documented QA workflow

### Stage 2 Archived (former deprecate set)
- `scripts/_archive/setup/test_api_paths.py`
- `scripts/_archive/setup/test_recipe_paths.py`
- `scripts/_archive/setup/test_web_config.py`
- `scripts/_archive/setup/test_anonymization.py`
- `scripts/_archive/ci/test_api_paths.py`
- `scripts/_archive/ci/test_recipe_paths.py`
- `scripts/_archive/ci/test_web_config.py`
- `scripts/_archive/ci/test_anonymization.py`
- `scripts/_archive/ci/test_participants_mapping.py`
- `scripts/_archive/ci/test_sav_anonymization.py`
  - archived from active paths because they are ad-hoc checks not wired into current GH Actions `ci.yml`

### Archive Candidate (web-unused, niche/dev)
- `scripts/future_feature/build_environment_from_dicom.py` (future feature; not implemented yet)
- `scripts/future_feature/build_environment_from_survey.py` (future feature; not implemented yet)
- `scripts/_archive/data/harvest_psytoolkit.py` (archived in stage 3)
- `scripts/_archive/data/anonymize_sav_files.py` (archived in stage 3)
- `scripts/_archive/dev/find_duplicates.py` (archived in stage 1)
- `scripts/_archive/dev/diagnose_duplicates.py` (archived in stage 1)
- `scripts/_archive/maintenance/generate_recipes.py` (archived in stage 4)
- `scripts/_archive/release/bundle_pyedflib.py` (archived in stage 4)
- Most of `app/helpers/**` except `app/helpers/physio/convert_varioport.py`

## Suggested Low-Risk Removal Order
1. Archive `scripts/dev/find_duplicates.py` first. ✅ Done
   - no CLI/web integration, pure ad-hoc scanner
2. Archive `scripts/dev/diagnose_duplicates.py`. ✅ Done
3. Move non-critical `scripts/setup/test_*.py` and `scripts/ci/test_*.py` to `scripts/_archive/`.
  - keep `scripts/ci/test_bids_compliance.py` for now ✅ Done
4. Review data scripts (`scripts/data/*.py`) with domain owners; archive if no current ops usage. ✅ Done
  - exception: two environment scripts moved to `scripts/future_feature/` because they are not implemented yet
5. Keep helper scripts for now, but split into:
   - runtime-critical (`convert_varioport.py`)
   - manual utilities (archive candidates)

## Roadmap
- [x] Analysis complete: web-runtime dependency graph mapped.
- [x] Stages 1-4 complete on `chore/script-cleanup-stage1-dev-archive`.
- [x] Archived sets complete:
  - `scripts/_archive/dev/*`
  - `scripts/_archive/setup/*`
  - `scripts/_archive/ci/*` (except active `scripts/ci/test_bids_compliance.py`)
  - `scripts/_archive/data/*` (except environment scripts)
  - `scripts/_archive/maintenance/*`
  - `scripts/_archive/release/*`
- [x] Future-feature set defined:
  - `scripts/future_feature/build_environment_from_dicom.py`
  - `scripts/future_feature/build_environment_from_survey.py`
- [ ] Optional follow-up: create a short `scripts/README.md` with active vs archived vs future-feature categories.
- [ ] Optional follow-up: run a focused smoke check (`tests/verify_repo.py` selected checks) before merge.

## Lessons Learned
- "Not used by web" is not the same as "unused": build and CLI workflows keep many scripts alive.
- Legacy wrappers/documentation can make low-usage scripts look active; check workflows and command handlers first.
- A safe release cleanup should be staged (dev -> setup/ci helpers -> data scripts) with documentation updates in lockstep.
- Backend-first architecture holds best when frontend stays orchestration-only and transformation logic is centralized in backend modules.
- Archiving (instead of deleting) keeps rollback easy while reducing active surface area before release.
- Keeping audit docs and validation allowlists in sync with script moves avoids accidental CI friction during release prep.
- Distinguishing `future_feature` from `archive` avoids signaling unfinished work as deprecated.
