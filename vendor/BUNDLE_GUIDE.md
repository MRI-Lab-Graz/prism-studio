# How to Bundle Pre-compiled pyedflib for Windows

## Quick Guide for Using Your Windows VM

### Step 1: Install pyedflib on Windows VM

1. Open Command Prompt or PowerShell on your Windows VM
2. Navigate to your Python environment:
   ```cmd
   cd C:\path\to\your\python\environment
   ```

3. Install pyedflib:
   ```cmd
   pip install pyedflib
   ```

4. Find where it was installed:
   ```cmd
   python -c "import pyedflib, os; print(os.path.dirname(pyedflib.__file__))"
   ```
   
   This will show something like:
   ```
   C:\Users\YourName\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyedflib
   ```

### Step 2: Copy Files from Windows VM to Mac

Copy the **entire pyedflib folder** from the Windows VM to your Mac:

**On Windows VM:**
- Navigate to the site-packages directory shown above
- Copy the `pyedflib` folder (entire folder!)
- Transfer it to your Mac (via shared folder, USB, network, etc.)

**On Mac:**
Paste it into: `/path/to/psycho-validator/vendor/`

Your structure should look like:
```
vendor/
├── pyedflib/
│   ├── __init__.py
│   ├── *.py (Python files)
│   ├── *.pyd (Windows compiled extensions)
│   └── ... (other package files)
├── __init__.py (loader)
└── README.md
```

### Step 3: Test It

```bash
cd /path/to/psycho-validator
source .venv/bin/activate
python -c "import sys; sys.path.insert(0, 'vendor'); import pyedflib; print('Success!', pyedflib.__version__)"
```

### Step 4: Commit to Repository

```bash
git add vendor/pyedflib/
git commit -m "Bundle pre-compiled pyedflib for Windows"
git push
```

## Alternative: Download Pre-built Wheel

If you want a cleaner approach:

```bash
# On your Mac:
cd /path/to/psycho-validator/vendor
mkdir -p wheels

# Download Windows wheels for different Python versions
pip download pyedflib --dest wheels --platform win_amd64 --python-version 311 --only-binary=:all:
pip download pyedflib --dest wheels --platform win_amd64 --python-version 310 --only-binary=:all:
pip download pyedflib --dest wheels --platform win_amd64 --python-version 39 --only-binary=:all:
```

Then Windows users can install with:
```cmd
pip install vendor\wheels\pyedflib-*.whl
```

## What Gets Committed

The vendor directory will contain:
- **pyedflib package** (~500KB-2MB): All Python and compiled files
- **Wheels** (optional, ~500KB each): For manual installation

## For Your IT Department

Tell them:
> "We're including a pre-compiled version of pyedflib in our repository. 
> Windows users don't need to install anything extra or compile code. 
> The .pyd files are already compiled and ready to use."

## Size Impact

- pyedflib package: ~1-2 MB
- Multiple wheels: ~500 KB each

Total repo size increase: ~2-5 MB (minimal)
