# Step-by-Step: Bundle pyedflib from Windows VM

## What You're Doing
Installing pyedflib on your Windows VM and copying the compiled files into the PRISM repository so Windows users don't need a C++ compiler.

---

## ON WINDOWS VM

### 1. Open PowerShell or Command Prompt

### 2. Install pyedflib
```cmd
pip install pyedflib
```

You should see output like:
```
Collecting pyedflib
  Downloading pyedflib-1.x.x-cpXXX-cpXXX-win_amd64.whl (XXX kB)
Successfully installed pyedflib-1.x.x
```

### 3. Find the Installation Directory
```cmd
python -c "import pyedflib, os; print(os.path.dirname(pyedflib.__file__))"
```

Output will be something like:
```
C:\Users\YourName\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyedflib
```

### 4. Open that folder in Explorer
```cmd
explorer C:\Users\YourName\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyedflib
```

### 5. Copy the ENTIRE `pyedflib` folder

Right-click the `pyedflib` folder → Copy

---

## ON YOUR MAC

### 6. Paste into vendor directory

Open Finder and navigate to:
```
/path/to/psycho-validator/vendor/
```

Paste the `pyedflib` folder there.

### 7. Verify the Structure

Open Terminal and check:
```bash
cd /path/to/psycho-validator
ls -la vendor/pyedflib/
```

You should see files including:
- `__init__.py`
- Various `.py` files
- `*.pyd` files (compiled Windows extensions)

### 8. Test It

```bash
./scripts/ci/test_pyedflib.sh
```

Should show: `✓ pyedflib is working correctly!`

### 9. Add to Git

```bash
git status
# Should show vendor/pyedflib/ files

git add vendor/pyedflib/
git add vendor/*.md
git add scripts/ci/test_pyedflib.*
git add .gitignore

git commit -m "Bundle pre-compiled pyedflib for Windows users without C++ compiler"
```

### 10. Push to Repository

```bash
git push
```

---

## What Windows Users Will Get

When they clone/download your repository:

1. **Automatic**: PRISM will find and use `vendor/pyedflib/` automatically
2. **No installation needed**: No pip install, no C++ compiler
3. **EDF support works**: Can extract metadata from EDF/EDF+ files

They can verify with:
```cmd
scripts\ci\test_pyedflib.bat
```

---

## File Sizes

The `pyedflib` folder is typically 1-2 MB, which is negligible for your repository.

Files you're committing:
- `vendor/pyedflib/`: ~1-2 MB (the actual package)
- `vendor/*.md`: Documentation
- `test_pyedflib.*`: Test scripts

---

## Troubleshooting

**If the test fails on Mac:**
- That's OK! The Windows-compiled `.pyd` files won't work on Mac
- They will work when Windows users clone the repo

**If you want to support multiple Python versions:**
- Repeat steps 1-5 with Python 3.9, 3.10, 3.11 on Windows
- Copy each to `vendor/pyedflib_py39/`, `vendor/pyedflib_py310/`, etc.
- (Advanced: modify `vendor/__init__.py` to detect Python version)

**For simplicity, just use one Python version (3.10 or 3.11 recommended)**

---

## Alternative: Quick Download Method

If you prefer not to use your Windows VM:

```bash
# On your Mac:
cd /path/to/psycho-validator/vendor
mkdir -p wheels

# Download pre-compiled wheels
pip download pyedflib --dest wheels --platform win_amd64 --python-version 311 --only-binary=:all:

# Extract the wheel (it's a ZIP file)
cd wheels
unzip pyedflib-*.whl -d ../
```

This downloads from PyPI (no VM needed) but wheels need manual installation by users.
