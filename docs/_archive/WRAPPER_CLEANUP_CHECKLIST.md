# Wrapper Cleanup Checklist

Status: Completed on 2026-02-26 (user-directed immediate cleanup)

This checklist defines when and how to remove temporary root-level script wrappers introduced during `scripts/` reorganization.

## Scope

Wrappers removed from old root paths:

- `scripts/anonymize_sav_files.py` -> `scripts/_archive/data/anonymize_sav_files.py` (archived)
- `scripts/build_environment_from_dicom.py` -> `scripts/future_feature/build_environment_from_dicom.py` (future feature)
- `scripts/build_environment_from_survey.py` -> `scripts/future_feature/build_environment_from_survey.py` (future feature)
- `scripts/harvest_psytoolkit.py` -> `scripts/_archive/data/harvest_psytoolkit.py` (archived)
- `scripts/diagnose_duplicates.py` -> `scripts/_archive/dev/diagnose_duplicates.py` (archived)
- `scripts/find_duplicates.py` -> `scripts/_archive/dev/find_duplicates.py` (archived)
- `scripts/generate_recipes.py` -> `scripts/_archive/maintenance/generate_recipes.py` (archived)
- `scripts/bundle_pyedflib.py` -> `scripts/_archive/release/bundle_pyedflib.py` (archived)
- `scripts/test_bids_compliance.py` -> `scripts/ci/test_bids_compliance.py`
- `scripts/test_sav_anonymization.py` -> `scripts/_archive/ci/test_sav_anonymization.py` (archived)
- `scripts/test_participants_mapping.py` -> `scripts/_archive/ci/test_participants_mapping.py` (archived)
- `scripts/test_pyedflib.sh` -> `scripts/ci/test_pyedflib.sh`
- `scripts/test_pyedflib.bat` -> `scripts/ci/test_pyedflib.bat`
- `scripts/windows_workshop_preflight.ps1` -> `scripts/setup/windows_workshop_preflight.ps1`

## Exit Criteria (all required)

1. One release cycle has shipped with wrappers present.
2. Internal docs reference canonical script paths only.
3. CI, setup scripts, and helper runners reference canonical script paths only.
4. No external automation dependency remains on wrapper paths (team confirmation).
5. Focused regression checks pass after wrapper deletion.

## Removal Procedure

1. Re-scan the repository for legacy wrapper paths:
   - `scripts/<old-name>` references for all items listed above.
2. Update any remaining references to canonical paths.
3. Remove wrapper files at root `scripts/` paths. ✅ Done
4. Keep canonical scripts in their domain folders unchanged.
5. Re-run validations:
   - `pytest -q tests/test_prism_tools_cli_contract.py tests/test_reorganization.py`
   - `python tests/verify_repo.py --check unsafe-patterns`
6. Add changelog entry describing wrapper removal and canonical paths. ✅ Done

## Suggested PR Title

`chore(scripts): remove legacy root wrappers after migration grace period`

## Rollback Plan

If breakage is reported after merge:

1. Re-introduce only affected wrappers as a hotfix.
2. Patch missed references to canonical paths.
3. Re-run focused tests and safety scan.
4. Retry full wrapper removal in next maintenance PR.
