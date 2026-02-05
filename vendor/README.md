# Vendored Dependencies

This directory contains pre-compiled packages for systems where compilation is not possible.

## pyedflib (Optional)

For Windows systems without C++ compiler:

1. **Download pre-compiled wheel:**
   ```bash
   pip download pyedflib --dest ./vendor/wheels --platform win_amd64 --python-version 311 --only-binary=:all:
   ```

2. **Extract the wheel:**
   ```bash
   # Wheels are just ZIP files
   unzip vendor/wheels/pyedflib-*.whl -d vendor/
   ```

3. **The tool will automatically use vendored packages if found**

## Alternative: Download from PyPI

Most Windows users can install directly:
```bash
pip install pyedflib
```

Pre-built wheels are available for:
- Python 3.8, 3.9, 3.10, 3.11
- Windows (win32, win_amd64)
- Linux (manylinux)
- macOS

If your IT department blocks compilation but allows pip, the wheel should install without issues.
