# Distributing Prism Validator for Windows

This guide covers how to build and distribute the Prism Validator as a standalone Windows `.exe` for beta testers.

## For Beta Testers (End Users)

**You don't need to install anything!**

1. Download `PrismValidator.exe` from the releases
2. Double-click to run
3. Your browser will automatically open with the validation interface
4. When finished, close the browser and the terminal window

### Troubleshooting for Users

- **Windows Defender Warning**: Click "More info" → "Run anyway" (the app is unsigned).
- **SmartScreen "Unknown Publisher"**: This is expected for unsigned open-source software. Adding version metadata (which we do) helps, but only a paid certificate removes this completely.
- **Firewall Prompt**: Click "Allow" - the app runs a local web server on your computer only.
- **Browser doesn't open**: Visit `http://localhost:5001` manually.

---

## SmartScreen and Code Signing

Microsoft Defender SmartScreen flags any executable that is not signed with a trusted Code Signing Certificate.

### Why the warning appears
1. **No Digital Signature**: The `.exe` is not signed by a Certificate Authority (CA).
2. **Low Reputation**: SmartScreen uses a reputation-based system. New files or files with few downloads are flagged until they "earn" reputation.

### How we improve this
- **Version Metadata**: We embed version information (Company, Product Name, Version) into the `.exe` using PyInstaller's `--version-file`. This makes the file look more legitimate to the OS.
- **Icon**: We bundle a high-resolution icon.

### How to fully remove the warning
To completely eliminate the warning, the executable must be signed using `signtool.exe` with a valid certificate (e.g., from Sectigo, DigiCert). This typically costs $200-$500/year.

If you have a certificate, you can sign the build:
```powershell
signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /a dist\PrismValidator\PrismValidator.exe
```

---

## For Developers (Building the .exe)

### Prerequisites

- A **Windows machine** (native or VM) - PyInstaller must build on the target OS
- Python 3.8+ installed with "Add to PATH" enabled
- Git (for cloning the repository)

### Quick Build (Recommended)

```powershell
# 1. Clone the repository
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio

# 2. Run the build script
.\scripts\build\build_windows.ps1
```

The executable will be at: `dist\PrismValidator.exe`

### Build Options

```powershell
# Default: Single-file windowed app (no console)
python scripts/build/build_app.py

# With console window (useful for debugging)
python scripts/build/build_app.py --console

# Build as folder instead of single file (faster startup)
python scripts/build/build_app.py --mode onedir

# Clean build (removes old artifacts)
python scripts/build/build_app.py --clean-output
```

### Distribution Checklist

Before distributing to beta testers:

- [ ] Build on a fresh Windows VM (ensures all dependencies are bundled)
- [ ] Test the `.exe` on a machine WITHOUT Python installed
- [ ] Test with a sample PRISM dataset
- [ ] Verify the browser opens automatically
- [ ] Verify validation results display correctly

### File Size

Expect the single-file `.exe` to be ~50-80 MB. This includes:
- Python runtime
- Flask web server
- All dependencies (numpy, pandas, jsonschema, etc.)
- Web templates and static files
- JSON schemas

---

## Alternative: GitHub Actions Automated Build

You can set up automatic builds using GitHub Actions. Add this workflow:

`.github/workflows/build-windows.yml`

```yaml
name: Build Windows Executable

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-windows:
    runs-on: windows-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-build.txt
        
    - name: Create survey_library directory
      run: |
        New-Item -ItemType Directory -Path survey_library -Force
        New-Item -ItemType File -Path survey_library\.gitkeep -Force
        
    - name: Build executable
      run: python scripts/build/build_app.py
      
    - name: Upload artifact
      uses: actions/upload-artifact@v4
      with:
        name: PrismValidator-Windows
        path: dist/PrismValidator.exe
        
    - name: Create Release
      if: startsWith(github.ref, 'refs/tags/')
      uses: softprops/action-gh-release@v1
      with:
        files: dist/PrismValidator.exe
```

Then:
1. Push a tag like `v1.0.0-beta1` 
2. GitHub automatically builds and publishes the `.exe`
3. Share the download link with testers

---

## Technical Details

### What the `.exe` Contains

- **Entry point**: `prism-studio.py` (Flask web interface)
- **Bundled data**: 
  - `templates/` - HTML templates
  - `static/` - CSS, JS, images
  - `schemas/` - PRISM validation schemas
  - `src/` - Core validation logic
  - `survey_library/` - Survey definitions (if present)

### How It Works

1. User runs `PrismValidator.exe`
2. PyInstaller extracts bundled files to a temp directory
3. Flask server starts on `localhost:5001`
4. Default browser opens automatically
5. User interacts via web interface
6. On exit, temp files are cleaned up

### Security Notes

- The app only listens on `localhost` by default (not network-accessible)
- No data is sent to external servers
- All validation happens locally
