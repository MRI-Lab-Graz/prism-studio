# Scripts Overview

This folder contains utility and operational scripts used around PRISM.

Scope reminder:
- PRISM web runtime is driven by backend modules under `app/src/**` and `src/**`.
- Scripts in this directory are mostly CI/build/setup/manual tooling.
- `prism.py` remains the main validator entrypoint.

## Active Categories

### `scripts/build/`
Build and packaging automation.

Active files:
- `scripts/build/build_app.py`
- `scripts/build/build_macos_app.sh`
- `scripts/build/build_windows.bat`
- `scripts/build/build_windows.ps1`

### `scripts/ci/`
CI and local smoke-check utilities.

Active files:
- `scripts/ci/assemble_portable_windows.ps1`
- `scripts/ci/run_local_smoke.bat`
- `scripts/ci/run_local_smoke.sh`
- `scripts/ci/run_runtime_gate.bat`
- `scripts/ci/run_runtime_gate.sh`
- `scripts/ci/test_bids_compliance.py`
- `scripts/ci/test_fresh_install.bat`
- `scripts/ci/test_fresh_install.ps1`
- `scripts/ci/test_pyedflib.bat`
- `scripts/ci/test_pyedflib.sh`

### `scripts/setup/`
Environment setup and global library configuration.

Active files:
- `scripts/setup/configure_global_library.py`
- `scripts/setup/setup-simple.sh`
- `scripts/setup/setup-windows.bat`
- `scripts/setup/setup.bat`
- `scripts/setup/setup.sh`
- `scripts/setup/show_global_config.py`
- `scripts/setup/verify_global_library.py`
- `scripts/setup/windows_workshop_preflight.ps1`

## Future Feature

### `scripts/future_feature/`
Planned scripts that are intentionally not part of active runtime/CI flows yet.

Files:
- `scripts/future_feature/build_environment_from_dicom.py`
- `scripts/future_feature/build_environment_from_survey.py`

## Archived

### `scripts/_archive/`
Deprecated or low-priority scripts retained for traceability and rollback.

Subfolders:
- `scripts/_archive/ci/`
- `scripts/_archive/data/`
- `scripts/_archive/dev/`
- `scripts/_archive/maintenance/`
- `scripts/_archive/release/`
- `scripts/_archive/setup/`

## Notes

- `scripts/data/`, `scripts/dev/`, `scripts/maintenance/`, and `scripts/release/` are intentionally empty in active use after cleanup.
- `__pycache__/` folders may appear locally during execution and are not part of the curated script inventory.
