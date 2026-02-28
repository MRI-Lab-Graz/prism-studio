# Installation

Get PRISM Studio running in 5 minutes.

## Quick Start

### macOS / Linux

```bash
# Clone and setup
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
./setup.sh

# Launch PRISM Studio
python prism-studio.py
```

Your browser will open automatically at `http://localhost:5001`

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
If the browser doesn't open automatically on Windows, manually navigate to `http://localhost:5001`
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
- ✅ Check **"Add Python to PATH"**
- ✅ Check **"tcl/tk and IDLE"** (required for folder picker)

---

## Installation Options

### Option 1: PRISM Studio (Recommended)

The web interface is the easiest way to use PRISM:

```bash
python prism-studio.py
```

Features:
- Project management with YODA layout
- Data conversion from Excel/CSV/SPSS
- Interactive validation with error explanations
- Survey library browser
- Recipe-based scoring

### Option 2: Command Line (CLI)

For scripting and batch processing:

```bash
# Validate a dataset
python prism.py /path/to/dataset

# Run recipes
python prism_tools.py recipes survey --prism /path/to/dataset
```

See the [CLI Reference](CLI_REFERENCE.md) for all commands.

### Option 3: Standalone Executable (Windows)

For users who don't want to install Python:

1. Download `PrismValidator.exe` from [GitHub Releases](https://github.com/MRI-Lab-Graz/prism-studio/releases)
2. Extract and run

```{note}
The standalone version includes validation only. For the full PRISM Studio experience with conversion and scoring, use the Python installation.
```

---

## Verify Installation

```bash
# Check version
python prism.py --version

# Run a test validation
python prism.py examples/workshop/exercise_1_raw_data
```

Expected output:
```
PRISM v1.9.1
Validating: examples/workshop/exercise_1_raw_data
...
```

## Daily Health Checks (Run-First)

In repo root:

```bash
# quick local sanity
bash scripts/ci/run_local_smoke.sh

# full required gate
bash scripts/ci/run_runtime_gate.sh
```

Windows:

```bat
scripts\ci\run_local_smoke.bat
scripts\ci\run_runtime_gate.bat
```

---

## Updating PRISM

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
# Check Python version
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

### Windows SmartScreen Warning

The standalone `.exe` may trigger SmartScreen warnings. This is normal for open-source software. See [Windows Setup](WINDOWS_SETUP.md) for details.

### Folder Picker Not Working

On Linux, install tkinter:
```bash
sudo apt-get install python3-tk
```

### EDF/EDF+ Support (Optional)

PRISM can extract metadata from EDF files if `pyedflib` is installed. **This is optional** – PRISM works fine without it.

**Most users:** `pyedflib` installs automatically via `setup.sh`/`setup.ps1`

**Windows users without C++ compiler:** Pre-compiled `pyedflib` is bundled in `vendor/`. Test it:
```batch
scripts\test_pyedflib.bat
```

If you see "✓ SUCCESS", EDF support is working. If not, you can:
- Use the bundled version (no action needed – it's automatic)
- Or install manually: `pip install pyedflib` (requires Visual C++ compiler)

See `vendor/BUNDLE_GUIDE.md` for details.

---

## Next Steps

- **[Quick Start](QUICK_START.md)** – Create your first project
- **[Workshop](WORKSHOP.md)** – Hands-on exercises
- **[Studio Overview](STUDIO_OVERVIEW.md)** – Tour of the web interface
