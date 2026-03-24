# Installation

Get PRISM Studio running in 5 minutes.

```{important}
PRISM Studio is the primary software interface for most users.
Use the validator CLI (`prism-validator`) for automation, CI, and advanced terminal workflows.
```

## Quick Start

### Fastest Path: Prebuilt Release (Recommended)

1. Open releases: https://github.com/MRI-Lab-Graz/prism-studio/releases
2. Download the package for your OS (Windows, macOS, or Linux).
3. Extract the archive.
4. Start PRISM Studio from the extracted folder.

Prebuilt startup behavior:
- PRISM Studio opens a dedicated terminal window by default so you can see backend logs and stop with `Ctrl+C`.
- To disable this, set `"showDedicatedTerminal": false` in your PRISM Studio user settings file (`prism_studio_settings.json`).

macOS first launch:
- If macOS blocks the app, double-click `Prism Studio Installer.app` in the extracted folder.
- This launcher checks quarantine state and only runs the first-launch fix when needed.
- On later launches (after quarantine is removed), it opens `PrismStudio.app` directly.
- If macOS security translocation hides neighboring files, the installer will ask you to select `PrismStudio.app` once.
- If launcher app is blocked, use `Open Prism Studio.command` instead.
- Both helpers remove quarantine metadata from `PrismStudio.app` and start the app.
- If needed, use Finder fallback: right-click `PrismStudio.app` -> Open -> Open.
- Apple guide for "Open Anyway": https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac

This is the quickest path and does not require repository setup.

### Alternative: Install from Source (macOS / Linux)

```bash
# Clone and setup
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
./setup.sh

# Launch PRISM Studio
python prism-studio.py
```

Your browser will open automatically at `http://localhost:5001`.

### Windows

```powershell
# Clone and setup
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
.\setup.ps1

# Launch PRISM Studio
python prism-studio.py
```

```{tip}
If the browser does not open automatically on Windows, navigate to `http://localhost:5001`.
```

---


## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.9+ | [Download](https://www.python.org/downloads/) |
| **Git** | Any | [Download](https://git-scm.com/downloads) |
| **Deno** | Optional | For BIDS validation (auto-installed by setup) |

### Windows-Specific Notes

When installing Python on Windows, make sure to:
- Check **"Add Python to PATH"**
- Check **"tcl/tk and IDLE"** (required for folder picker)

---

## Installation Options

### Option 1: Prebuilt PRISM Studio (Recommended)

Use this if you want the fastest start with minimal setup:

1. Download from releases: https://github.com/MRI-Lab-Graz/prism-studio/releases
2. Extract and launch PRISM Studio.

```{note}
Prebuilt packages are intended for normal end users. They are the preferred quickstart path.
```

### Option 2: PRISM Studio from Source

Use source installation if you need development workflows or custom local changes.

The web interface is still the default way to use PRISM Studio:

```bash
python prism-studio.py
```

Features:
- Project management with YODA layout
- Data conversion from Excel/CSV/SPSS
- Interactive validation with error explanations
- Survey library browser
- Recipe-based scoring

### Option 3: Command Line (Optional)

For scripting and batch processing:

```bash
# Validate a dataset
python prism-validator /path/to/dataset

# Run recipes
python prism_tools.py recipes survey --prism /path/to/dataset
```

See the [CLI Reference](CLI_REFERENCE.md) for all commands.

### Option 4: Validator-Only Binary (Windows)

If you only need validation (without full Studio workflows), use `PrismValidator.exe` from releases.

---

## Verify Installation

Primary check (recommended):

```bash
python prism-studio.py
```

If Studio opens at `http://localhost:5001`, installation is successful.

For prebuilt installs, successful launch of the bundled app from the extracted release folder is sufficient.

Optional CLI check:

```bash
python prism-validator --version
```

---

## Updating PRISM Studio

```bash
cd prism-studio
git pull
pip install -r requirements.txt
```

---

## Troubleshooting

### "Python not found"

Make sure Python is in your PATH:

```bash
python --version
# or
python3 --version
```

### "Module not found" errors

Activate the virtual environment first:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### Windows SmartScreen warning

The standalone `.exe` may trigger SmartScreen warnings. This is normal for open-source software.

### macOS Gatekeeper warning

Unsigned or non-notarized macOS apps can be blocked on first launch after download.

Use the bundled helper script in the extracted release folder:

```bash
./Open\ Prism\ Studio.command
```

Preferred helper (double-click in Finder): `Prism Studio Installer.app`

If Finder still shows a warning, right-click `PrismStudio.app` and choose Open once.

Official Apple instructions for "Open Anyway":
https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac

```{note}
Full out-of-the-box trust on macOS typically requires Apple Developer ID signing and notarization.
Without notarization, Gatekeeper prompts are expected for downloaded binaries.
```

### Folder picker not working

On Linux, install tkinter:

```bash
sudo apt-get install python3-tk
```

### EDF/EDF+ support (optional)

PRISM Studio can extract metadata from EDF files if `pyedflib` is installed. This is optional.

Most users: `pyedflib` installs automatically via `setup.sh` or `setup.ps1`.

Windows users without a C++ compiler: pre-compiled `pyedflib` is bundled in `vendor/`. Test it:

```bat
scripts\test_pyedflib.bat
```

If you see `SUCCESS`, EDF support is working. If not, you can:
- Use the bundled version (automatic)
- Or install manually: `pip install pyedflib` (requires Visual C++ compiler)

See `vendor/BUNDLE_GUIDE.md` for details.

---

## Next Steps

- [Quick Start](QUICK_START.md): Create your first project
- [Workshop](WORKSHOP.md): Hands-on exercises
- [Studio Overview](STUDIO_OVERVIEW.md): Tour of the web interface
