# Vendored Dependencies

This directory contains pre-compiled packages for systems where compilation is not possible.

## ⚡ Recommended: Use `uv` for Installation

**Best approach for all users (no C++ compiler needed):**

```bash
# Install using uv (works without C++ compiler)
uv pip install pyedflib
```

This works even on:
- Python 3.14+ ARM64 (Windows on ARM)
- Systems without Visual C++ Build Tools  
- Fresh installations without compiler toolchains

## Alternative: Regular pip

Most Windows users can install directly:
```bash
pip install pyedflib
```

Pre-built wheels are available for:
- Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13
- Windows (win32, win_amd64)
- Linux (manylinux)
- macOS

**Note:** For Python 3.14+ or ARM64, use `uv` instead.
