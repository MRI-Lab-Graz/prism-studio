# Fresh Installation Guide

Complete guide for installing PRISM Validator from scratch on Windows, macOS, and Linux.

## Quick Start (Any Platform)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/prism-validator.git
cd prism-validator

# 2. Run setup script
# Windows:
.\setup.ps1

# macOS/Linux:
bash setup.sh

# 3. Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1

# macOS/Linux:
source .venv/bin/activate

# 4. Verify installation
python prism.py --help
```

That's it! The setup script handles everything automatically.

---

## Architecture Compatibility

### Windows

| Architecture | pyedflib Installation | Notes |
|--------------|----------------------|-------|
| **x64 (AMD64)** | ✅ `pip` or `uv` | Pre-built wheels available for Python 3.8-3.13 |
| **ARM64** | ⚠️ Requires `uv` | No pre-built wheels - `uv` builds automatically |
| **x86 (32-bit)** | ⚠️ Limited support | May require manual compilation |

**Your VM is ARM64** - This is the most challenging case, but `uv` handles it perfectly!

**Most Windows users have x64** - pyedflib installs easily with regular `pip` for Python 3.8-3.13.

### macOS

| Architecture | pyedflib Installation | Notes |
|--------------|----------------------|-------|
| **Apple Silicon (M1/M2/M3)** | ✅ `pip` or `uv` | Pre-built wheels available |
| **Intel (x86_64)** | ✅ `pip` or `uv` | Full support |

### Linux

| Architecture | pyedflib Installation | Notes |
|--------------|----------------------|-------|
| **x86_64** | ✅ `pip` or `uv` | Manylinux wheels available |
| **ARM64** | ⚠️ Requires `uv` | Limited wheel availability |
| **ARM (32-bit)** | ⚠️ Requires compilation | May need build tools |

---

## Detailed Installation Steps

### 1. Prerequisites

**All Platforms:**
- Git
- Python 3.9 or later (Python 3.10-3.12 recommended)
- Internet connection

**Optional (but recommended):**
- `uv` package manager (setup script will offer to install it)

**Windows-specific:**
- For folder picker: Ensure "tcl/tk and IDLE" was checked during Python installation
- For BIDS validation: Deno (setup script will install automatically)

**Linux-specific:**
- tkinter: `sudo apt-get install python3-tk` (Ubuntu/Debian) or `sudo dnf install python3-tkinter` (Fedora/RHEL)
- Deno: Will be installed automatically by setup script

### 2. Clone Repository

```bash
git clone https://github.com/your-org/prism-validator.git
cd prism-validator
```

### 3. Run Setup Script

**Windows:**
```powershell
.\setup.ps1
```

The script will:
1. ✅ Check for/install `uv` (highly recommended)
2. ✅ Check for Deno (BIDS validation)
3. ✅ Check for tkinter (folder picker)
4. ✅ Create `.venv` virtual environment
5. ✅ Install all dependencies from `requirements.txt`
6. ✅ Install PRISM in development mode

**Additional options:**
```powershell
# Include build dependencies (for creating standalone executable)
.\setup.ps1 -Build

# Include development dependencies (for testing/contributing)
.\setup.ps1 -Dev

# Both
.\setup.ps1 -Build -Dev
```

**macOS/Linux:**
```bash
bash setup.sh
```

**Additional options:**
```bash
# Include build dependencies
bash setup.sh --build

# Include development dependencies
bash setup.sh --dev

# Both
bash setup.sh --build --dev
```

### 4. Activate Virtual Environment

**Windows:**
```powershell
.\.venv\Scripts\Activate.ps1

# If you get execution policy errors:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

You'll see `(.venv)` in your prompt when activated.

### 5. Verify Installation

```bash
# Check PRISM is installed
python prism.py --version

# Check pyedflib is available (for RAW→EDF conversion)
python -c "import pyedflib; print('✅ pyedflib is available')"

# Run the test suite (optional)
pytest
```

---

## Troubleshooting

### pyedflib Won't Install

**Error:** `Microsoft Visual C++ 14.0 or greater is required`

**Solution:**
```powershell
# Install pyedflib using uv instead
uv pip install pyedflib
```

This works even without a C++ compiler!

**Why:** Regular `pip` tries to build from source on some platforms. `uv` has better package resolution and can install without compilation.

### tkinter Not Available

**Error:** `ModuleNotFoundError: No module named 'tkinter'`

**Impact:** Web interface folder picker won't work (you can still type paths manually)

**Windows Solution:**
1. Reinstall Python
2. During installation, check "tcl/tk and IDLE"

**Linux Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora/RHEL
sudo dnf install python3-tkinter
```

**macOS:** tkinter is included with Python

### Execution Policy Error (Windows)

**Error:** `.ps1 cannot be loaded because running scripts is disabled`

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ARM64 Virtual Machine Issues

**If you're running Windows ARM64 in a VM (Parallels, VMware):**

1. ✅ Use `uv` for package installation (already in setup script)
2. ⚠️ Performance may be slower than native x64
3. ✅ All features work, including RAW→EDF conversion

**Most real Windows PCs are x64 and won't have these issues!**

---

## Testing Your Installation

Run the comprehensive installation test:

```powershell
# Windows
.\scripts\ci\test_fresh_install.ps1

# Specific tests
.\scripts\ci\test_fresh_install.ps1 -TestVendored  # Test vendored pyedflib
.\scripts\ci\test_fresh_install.ps1 -TestPip       # Test pip installation
```

This will verify:
- ✅ Vendored pyedflib structure (fallback option)
- ✅ pyedflib import capability
- ✅ Fresh venv creation and package installation
- ✅ Current environment status

---

## What Gets Installed

### Core Dependencies
- `jsonschema` - Schema validation
- `Flask` - Web interface
- `numpy` - Numerical operations
- `pandas` - Data manipulation
- `Pillow` - Image processing
- `pyedflib` - EDF file support (optional)
- `bids-validator` - BIDS compliance checking
- And more... (see `requirements.txt`)

### Build Dependencies (Optional)
- `pyinstaller` - Create standalone executables
- `pytest` - Testing framework
- (see `requirements-build.txt`)

### Development Dependencies (Optional)
- `black` - Code formatting
- `flake8` - Linting
- `pytest` - Testing
- (see `requirements-dev.txt`)

---

## Platform-Specific Notes

### Windows x64 (Most Common) ✅ EASY

**Typical User Setup:**
- Python 3.10-3.12
- Windows 10/11 x64
- Internet access

**Installation:** Works perfectly with regular `pip` or `uv`. No compiler needed.

```powershell
.\setup.ps1
# Everything just works!
```

### Windows ARM64 (Virtual Machines) ⚠️ ADVANCED

**Your Setup:**
- Windows 11 ARM64 VM on macOS (Parallels/VMware)
- Python 3.14
- Limited pre-built wheels

**Installation:** Use `uv` for best results (setup script does this automatically)

```powershell
.\setup.ps1
# uv handles the tricky parts automatically
```

**Performance Note:** Conversion of large files may be slower in VM than on native hardware.

### macOS (All Versions) ✅ EASY

**Installation:** Works perfectly on both Intel and Apple Silicon

```bash
bash setup.sh
```

### Linux (All Distributions) ✅ MOSTLY EASY

**Installation:** Usually straightforward, may need tkinter package

```bash
# Install tkinter first (if needed)
sudo apt-get install python3-tk  # Ubuntu/Debian
sudo dnf install python3-tkinter  # Fedora/RHEL

# Then run setup
bash setup.sh
```

---

## Simulating Fresh Installation

To test how a new user would experience installation:

```powershell
# 1. Delete the virtual environment
Remove-Item -Recurse -Force .venv

# 2. Re-run setup
.\setup.ps1

# 3. Verify everything works
.\.venv\Scripts\Activate.ps1
python prism.py --help
```

---

## For Users Without Git

If users download a ZIP file instead of cloning:

1. Download ZIP from GitHub
2. Extract to a folder
3. Open PowerShell/Terminal in that folder
4. Run `setup.ps1` (Windows) or `bash setup.sh` (macOS/Linux)

---

## Offline Installation

For restricted environments without internet:

1. **On a connected machine:**
   ```bash
   # Download all dependencies
   pip download -r requirements.txt -d ./offline_packages
   ```

2. **Transfer `offline_packages/` folder to target machine**

3. **On target machine:**
   ```bash
   # Create venv
   python -m venv .venv
   
   # Activate venv
   .\.venv\Scripts\Activate.ps1  # Windows
   source .venv/bin/activate      # macOS/Linux
   
   # Install from local packages
   pip install --no-index --find-links ./offline_packages -r requirements.txt
   ```

---

## Next Steps After Installation

1. **Run the validator:**
   ```bash
   python prism.py /path/to/your/dataset
   ```

2. **Start the web interface:**
   ```bash
   python prism-studio.py
   # Opens browser to http://localhost:5001
   ```

3. **Convert data:**
   ```bash
   python prism_tools.py /path/to/source/folder /path/to/output/folder
   ```

4. **Read the documentation:**
   - [Quick Start Guide](QUICK_START.md)
   - [Validator Reference](VALIDATOR.md)
   - [Web Interface Guide](WEB_INTERFACE.md)
   - [Converter Tools](TOOLS.md)

---

## Getting Help

- 📖 Documentation: `docs/` folder
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions

## Summary for Your Situation

**You (Windows ARM64 VM):** Challenging case, but `uv` solves it ✅

**Most Windows users (x64):** Simple and straightforward ✅

**The setup script handles both cases automatically!** 🎉
