# macOS App Build (Private Notes)

This document describes how to build a local macOS `.app` bundle for PRISM.

It is intentionally **not included** in the official ReadTheDocs documentation stream:
- It lives under `docs/_private/`.
- It is **not referenced** from any Sphinx `toctree` (see `docs/index.rst`).

If you want it to show up on ReadTheDocs later, add it to a `toctree` explicitly.

---

## What you get

- Output: `dist/PrismValidator.app`
- Entry point: `prism-gui.py` (desktop GUI)
- Build tool: PyInstaller (installed via `requirements-build.txt`)

---

## Prerequisites

- macOS
- `uv` installed (required by this repo’s setup scripts)
- Xcode Command Line Tools recommended (for `codesign`, `plutil`, etc.)

The build uses the repo-local virtual environment at `./.venv`.

---

## Build steps (recommended)

From the repository root:

1) Install runtime + build dependencies using the setup script:

```bash
bash scripts/setup/setup.sh --build
```

2) Activate the virtual environment:

```bash
source .venv/bin/activate
```

3) Build the `.app` bundle:

```bash
bash scripts/build/build_macos_app.sh
```

4) Run the app:

```bash
open dist/PrismValidator.app
```

---

## What the build scripts do

- `scripts/setup/setup.sh --build`
  - creates/refreshes `./.venv`
  - installs `requirements.txt`
  - installs `requirements-build.txt` (currently just `pyinstaller`)

- `scripts/build/build_macos_app.sh`
  - verifies `./.venv` exists and is active
  - calls `python scripts/build/build_app.py --entry prism-gui.py --mode onedir`

- `scripts/build/build_app.py`
  - bundles required runtime folders into the app:
    - `src/`, `schemas/`, `templates/`, `static/`, and `survey_library/`
  - on macOS, generates an `.icns` from `static/img/MRI_Lab_Logo.png` (best-effort)
  - applies post-build fixes:
    - sets `LSMinimumSystemVersion` in `Info.plist`
    - ad-hoc signs the bundle (`codesign --deep --sign - ...`)
    - removes quarantine attributes (`xattr -cr ...`)

---

## Common troubleshooting

### “You are not running inside the prism virtual environment!”

Activate the venv first:

```bash
source .venv/bin/activate
```

### “PyInstaller not installed…”

Install build dependencies via setup script (preferred for this repo):

```bash
bash scripts/setup/setup.sh --build
```

### Icon generation fails

Icon generation on macOS uses `sips` and `iconutil` and is best-effort.
If it fails, the app should still build.

You can skip icon generation:

```bash
python scripts/build/build_app.py --entry prism-gui.py --name PrismValidator --mode onedir --no-icon
```

### Gatekeeper / “app is damaged” / prohibited sign

The build script already runs ad-hoc signing and removes quarantine flags.
If you move the `.app` between machines, macOS may re-apply quarantine.

On the target machine:

```bash
xattr -cr /path/to/PrismValidator.app
```

---

## Alternative: package the web interface instead

If you want a packaged app that starts the Flask web interface:

```bash
source .venv/bin/activate
python scripts/build/build_app.py --entry prism-studio.py --name PrismValidatorWeb --mode onefile --clean-output
```

Note: packaging the web server as a GUI app may require additional UX decisions (how to show logs/port, auto-opening the browser, etc.).
