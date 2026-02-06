# ✅ Windows pyedflib Checklist

## Current Status: Ready for Bundling

All infrastructure is in place. Just need the Windows files.

---

## ✅ Completed Setup

- [x] Created `vendor/` directory structure
- [x] Made `pyedflib` optional in requirements
- [x] Added to `setup.py` extras
- [x] Configured `.gitignore` to include vendor/
- [x] Created automatic loader (`vendor/__init__.py`)
- [x] Added test scripts (`.bat` and `.sh`)
- [x] Created comprehensive documentation
- [x] Added verification script

---

## 📋 What You Need to Do

### Step 1: On Windows VM (2 minutes)

```cmd
pip install pyedflib
python -c "import pyedflib, os; print(os.path.dirname(pyedflib.__file__))"
```

Copy the path shown, then:

```cmd
explorer [paste path here]
```

**Copy the entire `pyedflib` folder**

### Step 2: On Mac (1 minute)

Paste `pyedflib` folder into:
```
/Users/karl/work/github/prism-studio/vendor/
```

### Step 3: Verify (30 seconds)

```bash
cd /Users/karl/work/github/prism-studio
python vendor/verify_structure.py
```

Should show: `✅ VENDOR STRUCTURE LOOKS GOOD!`

### Step 4: Commit (30 seconds)

```bash
git add vendor/
git add test_pyedflib.*
git add .gitignore
git commit -m "Bundle pre-compiled pyedflib for Windows users

- Add vendor/ directory with pre-compiled pyedflib
- Windows users without C++ compiler can now use EDF files
- Optional dependency - PRISM works without it
- Includes test scripts and documentation"
git push
```

---

## 🎉 Done!

Windows users will get:
- ✅ EDF/EDF+ file support
- ✅ No C++ compiler needed
- ✅ No manual installation
- ✅ Works out of the box

---

## Alternative: Skip Bundling

If you decide **not** to bundle:

1. Keep `pyedflib` commented in `requirements.txt`
2. Document it as optional in README
3. Users who need EDF support can:
   - Try `pip install pyedflib` (works if they have compiler)
   - Request IT exception
   - Or skip EDF metadata extraction

PRISM will work fine either way!

---

## File Locations

Documentation:
- `vendor/SUMMARY.md` – This checklist
- `vendor/STEP_BY_STEP.md` – Detailed walkthrough
- `vendor/BUNDLE_GUIDE.md` – Technical details
- `docs/INSTALLATION.md` – User-facing docs

Scripts:
- `scripts/test_pyedflib.bat` – Windows test script
- `scripts/test_pyedflib.sh` – Mac/Linux test script
- `vendor/verify_structure.py` – Verify bundle

System:
- `vendor/__init__.py` – Auto-loader
- `.gitignore` – Configured to include vendor/

---

## Questions?

**Q: Will this work for all Python versions?**
A: Bundle from Python 3.10 or 3.11. It will work for that version. For multiple versions, repeat with each Python version.

**Q: How big is it?**
A: ~1-2 MB. Negligible.

**Q: Do Mac/Linux users need this?**
A: No. They can install normally. The vendor/ is a fallback.

**Q: What if I don't have a Windows VM?**
A: Use the download script: `python scripts/bundle_pyedflib.py`

**Q: Is this standard practice?**
A: Yes! Many Python packages vendor dependencies for platforms where compilation is difficult.
