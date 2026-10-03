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
- `scripts/build/build_windows_local.ps1` (local Windows build, same steps as CI)

### `scripts/ci/`
CI and local smoke-check utilities.

Active files:
- `scripts/ci/smoke_bundle_imports.py`
- `scripts/ci/smoke_packaged_web_app.py`
- `scripts/ci/test_fresh_install.bat`

### `scripts/setup/`
Environment setup and global library configuration.

The end-user installers are `install.cmd` / `install.sh` at the repo root
(the only two files a user should ever run to set up PRISM Studio); this
folder holds `install.cmd`'s implementation plus unrelated global-library
config tooling. Don't add another top-level setup/install script here or at
the repo root - that's the "which file do I run" confusion this layout
replaced.

Active files:
- `scripts/setup/configure_global_library.py`
- `scripts/setup/create_desktop_shortcut.ps1`
- `scripts/setup/verify_global_library.py`
- `scripts/setup/windows.ps1` (setup logic invoked by `install.cmd` at the repo root; not meant to be run directly)
- `scripts/setup/windows_workshop_preflight.ps1`

## Notes

- `scripts/release/` holds the macOS first-run files that `.github/workflows/build.yml` packages.
- Repo gate: `python tests/verify_repo.py --check entrypoints-smoke,import-boundaries,pytest --no-fix`.
- `__pycache__/` folders may appear locally during execution and are not part of the curated script inventory.
