# pyedflib Installation Guide

## Problem

Some Windows systems cannot install `pyedflib` via regular `pip` because:
1. **No pre-built wheels** for Python 3.14+ or ARM64 architecture
2. **Requires C++ compiler** (Visual Studio Build Tools) to build from source
3. Many corporate/restricted environments don't allow compiler installation

## Solution: Use `uv`

**✅ Recommended:** Install using `uv` which has superior package resolution:

```powershell
uv pip install pyedflib
```

### Why `uv` Works Better

- **Smarter dependency resolution**: Finds compatible versions automatically
- **No compiler needed**: Can install packages that regular pip can't
- **Cross-platform**: Works on ARM64, x64, and all Python versions
- **Faster**: Significantly quicker than regular pip

## Installation Methods (in order of preference)

### Method 1: uv (Recommended) ⭐

```bash
# Install uv first (if not already installed)
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Then install pyedflib
uv pip install pyedflib
```

### Method 2: Regular pip

```bash
pip install pyedflib
```

**Works for:** Python 3.8-3.13 on x64 Windows (if pre-built wheels available)  
**Fails for:** Python 3.14+, ARM64, or systems without wheels

### Method 3: Vendored Package (Fallback)

If all else fails, PRISM includes a vendored copy of pyedflib in the `vendor/` directory.

**Automatic fallback:** The tool will automatically use the vendored version if system installation fails.

## Verification

Test that pyedflib is working:

```bash
# Using venv Python
.venv\Scripts\python.exe -c "import pyedflib; print(f'✅ pyedflib {pyedflib.__version__}')"

# Or with uv
uv run python -c "import pyedflib; print('✅ Works!')"
```

## Fresh Installation Test

Run the comprehensive installation test:

```powershell
.\scripts\ci\test_fresh_install.ps1
```

This will:
1. ✅ Check for vendored pyedflib structure
2. ✅ Test vendored import
3. ✅ Simulate fresh venv installation
4. ✅ Report current environment status

## What Happens Without pyedflib?

PRISM will still work, but with reduced functionality:

- ❌ RAW files will be **copied** instead of **converted to EDF**
- ❌ No EDF metadata extraction
- ❌ No automatic heart rate estimation from ECG
- ⚠️ Less informative physio reports

## For IT Departments

**Question:** "Why does this need a compiler?"

**Answer:** pyedflib is a Python wrapper around C code for reading/writing EDF files (medical data format). Pre-built binaries exist for common platforms, but newer Python versions may require building from source.

**Solution:** Use `uv` instead of `pip` - no compiler needed!

## Technical Details

### Architecture Compatibility

| Python Version | x64 Windows | ARM64 Windows | Linux | macOS |
|----------------|-------------|---------------|-------|-------|
| 3.8-3.12      | ✅ pip works | ⚠️ use uv    | ✅    | ✅    |
| 3.13          | ⚠️ use uv   | ⚠️ use uv    | ⚠️    | ⚠️    |
| 3.14+         | ⚠️ use uv   | ⚠️ use uv    | ⚠️    | ⚠️    |

### Error: "Microsoft Visual C++ 14.0 or greater is required"

This means:
- No pre-built wheel available for your Python version/architecture
- pip is trying to build from source
- **Solution:** Use `uv pip install` instead

## See Also

- `vendor/README.md` - Vendored packages documentation
- [setup.ps1](../setup.ps1) - Setup script (uses uv by default)
- [INSTALLATION.md](INSTALLATION.md) - General installation guide
