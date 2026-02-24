# Windows 11 VMware VM: Build & Test Portable ZIP

This guide provides **copyable commands** for building and testing the PRISM Validator portable ZIP inside a Windows 11 VMware VM.

## Prerequisites (One-Time Setup)

### 1. Install Python 3.8+

Download and install: https://www.python.org/downloads/

✅ **Critical**: Check "Add Python to PATH" during installation

Verify installation:
```powershell
python --version
```

### 2. Install Git (Optional)

Download: https://git-scm.com/download/win

Or if you already have the code, skip this.

---

## Quick Build & Test (Copy-Paste Each Section)

### Step 1: Open PowerShell in Project Directory

```powershell
# Navigate to prism-validator directory
cd C:\Users\karl\github\prism-validator
```

### Step 2: Clean Previous Builds (Optional but Recommended)

```powershell
# Remove old build artifacts
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
```

### Step 3: Setup Environment with Build Dependencies

```powershell
# Run setup script with build flag
.\setup.ps1 -Build
```

**Expected Output:**
- Creates `.venv` folder
- Installs all dependencies
- Installs PyInstaller

### Step 4: Activate Virtual Environment

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your prompt.

### Step 5: Build the Application

```powershell
# Run the build script
python scripts\build\build_app.py
```

**Build Time:** ~2-5 minutes depending on VM resources

**Expected Output:**
```
Building PRISM Validator...
Version: 1.8.2
Creating Windows executable...
[... PyInstaller output ...]
✅ Build complete!
```

**Note:** This build uses `app/prism-studio.py` as the entry point (not the root `prism-studio.py` wrapper), which is required for the frozen exe to work correctly.

### Step 6: Verify Build Output

```powershell
# Check that executable exists
Test-Path .\dist\PrismValidator\PrismValidator.exe
```

Should return `True`

```powershell
# List contents of dist folder
Get-ChildItem .\dist\PrismValidator\ | Select-Object Name, Length
```

**Expected Files:**
- `PrismValidator.exe` (main executable, ~5-10 MB)
- `_internal/` folder (contains bundled Python runtime and dependencies)

**Note:** The `templates/`, `static/`, `schemas/`, and `src/` folders are **bundled inside the .exe file**, not as separate folders. This is PyInstaller's "onefile" mode - everything is packaged into the single executable.

### Step 7: Create Portable ZIP

```powershell
# Stop any running instances first (files must not be in use)
Get-Process -Name "PrismValidator" -ErrorAction SilentlyContinue | Stop-Process -Force

# Compress the entire directory into a ZIP
Compress-Archive -Path .\dist\PrismValidator\* -DestinationPath .\dist\PrismValidator-Portable.zip -Force
```

**Important:** The process must be stopped before creating the ZIP, otherwise files will be locked.

### Step 8: Verify ZIP File

```powershell
# Check ZIP file size and properties
Get-Item .\dist\PrismValidator-Portable.zip | Select-Object Name, Length, LastWriteTime
```

**Expected Size:** ~40-80 MB (since it's a onefile build with everything bundled in the .exe)

---

## Testing the Portable ZIP

### Test 1: Run Executable In-Place

```powershell
# Run the executable from dist folder
.\dist\PrismValidator\PrismValidator.exe

# Wait a few seconds, then check if it's running
Start-Sleep -Seconds 3
Get-Process -Name "PrismValidator" -ErrorAction SilentlyContinue

# If running, open browser manually (in case auto-open failed)
Start-Process "http://localhost:5001"
```

**Expected Behavior:**
- Process starts (check Task Manager or `Get-Process`)
- Web browser should auto-launch at `http://localhost:5001`
- No console window appears (since it's a GUI app)
- If browser doesn't auto-open, manually go to http://localhost:5001

**If nothing happens:**
- See [Troubleshooting: Executable Doesn't Launch](#executable-doesnt-launch--nothing-happens)

**To close:**
- Close browser tab
- Right-click system tray icon (if any) → Exit
- Or: `Get-Process PrismValidator | Stop-Process`

### Test 2: Extract ZIP to Temp Location

```powershell
# Create temp test directory
$TestDir = "$env:TEMP\PrismValidator-Test"
New-Item -ItemType Directory -Path $TestDir -Force

# Extract ZIP to temp location
Expand-Archive -Path .\dist\PrismValidator-Portable.zip -DestinationPath $TestDir -Force

# List extracted files
Get-ChildItem $TestDir | Select-Object Name
```

### Test 3: Run from Extracted Location

```powershell
# Run from temp directory
& "$TestDir\PrismValidator.exe"
```

**Expected Behavior:**
- Same as Test 1
- Application runs without dependencies
- Truly portable (no installation needed)

### Test 4: Validate with Demo Dataset

```powershell
# First, ensure app is running from Test 2/3
# Then manually:
# 1. Open browser to http://localhost:5001
# 2. Click "Choose Folder"
# 3. Navigate to: C:\Users\karl\github\prism-validator\demo
# 4. Click "Validate Dataset"
```

**Expected Result:**
- Validation completes
- Report shows dataset structure
- No errors for demo dataset

### Test 5: Check File Size & Dependencies

```powershell
# Check executable size
(Get-Item .\dist\PrismValidator\PrismValidator.exe).Length / 1MB

# Check _internal folder size
(Get-ChildItem .\dist\PrismValidator\_internal -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB

# Check total directory size
(Get-ChildItem .\dist\PrismValidator\ -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
```

**Expected Sizes:**
- `PrismValidator.exe`: ~5-10 MB (contains all your code and data files)
- `_internal/`: ~30-60 MB (Python runtime, libraries, dependencies)
- Total: ~40-80 MB

### Test 6: Test Without Virtual Environment

```powershell
# Deactivate venv
deactivate

# Remove Python from PATH temporarily (optional extreme test)
$env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notlike '*Python*' }) -join ';'

# Try running executable
.\dist\PrismValidator\PrismValidator.exe
```

**Expected Behavior:**
- Still works! (Proving it's truly standalone)

---

## Cleanup Test Environment

```powershell
# Remove temp test directory
Remove-Item -Recurse -Force "$env:TEMP\PrismValidator-Test" -ErrorAction SilentlyContinue

# Stop any running PrismValidator processes
Get-Process -Name "PrismValidator" -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## Troubleshooting

### Build Fails: "Python not found"

```powershell
# Check Python installation
python --version

# If not found, verify PATH
$env:PATH -split ';' | Select-String Python
```

### Build Fails: "Module not found"

```powershell
# Ensure you're in venv
.\.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
pip install -r requirements-build.txt
```

### Executable Doesn't Launch / Nothing Happens

**First, check if it's actually running:**

```powershell
# Check if process is running
Get-Process -Name "PrismValidator" -ErrorAction SilentlyContinue

# If running, try opening browser manually
Start-Process "http://localhost:5001"
```

**If not running, check for errors:**

```powershell
# Run with visible console to see errors
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\dist\PrismValidator'; .\PrismValidator.exe"
```

**Alternative: Check Windows Event Viewer:**

```powershell
# Check application event log for errors
Get-EventLog -LogName Application -Source "Application Error" -Newest 5 | Where-Object {$_.Message -like "*PrismValidator*"}
```

**Common issues:**
- Port 5001 already in use
- Missing dependencies in `_internal/` folder
- Antivirus blocking execution
- App crashes immediately on startup

### "Access Denied" or Antivirus Blocks

```powershell
# Temporarily disable Windows Defender (not recommended for production)
Set-MpPreference -DisableRealtimeMonitoring $true

# Add exclusion for dist folder
Add-MpPreference -ExclusionPath "C:\Users\karl\github\prism-validator\dist"

# Re-enable after testing
Set-MpPreference -DisableRealtimeMonitoring $false
```

### Port 5001 Already in Use

```powershell
# Find what's using port 5001
Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue

# Kill the process
Stop-Process -Id <PID> -Force
```

---

## Complete Start-to-Finish Script (Copy All)

```powershell
# ============================================
# PRISM Validator: Complete Build & Test
# ============================================

# Navigate to project
cd C:\Users\karl\github\prism-validator

# Clean previous builds
Write-Host "🧹 Cleaning previous builds..." -ForegroundColor Yellow
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue

# Setup environment
Write-Host "📦 Setting up environment..." -ForegroundColor Yellow
.\setup.ps1 -Build

# Activate venv
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1

# Build
Write-Host "🏗️ Building application..." -ForegroundColor Yellow
python scripts\build\build_app.py

# Verify build
Write-Host "✅ Verifying build..." -ForegroundColor Green
if (Test-Path .\dist\PrismValidator\PrismValidator.exe) {
    Write-Host "   Build successful!" -ForegroundColor Green
    $exeSize = (Get-Item .\dist\PrismValidator\PrismValidator.exe).Length / 1MB
    Write-Host "   Executable size: $($exeSize.ToString('F2')) MB" -ForegroundColor Cyan
} else {
    Write-Host "   ❌ Build failed - executable not found!" -ForegroundColor Red
    exit 1
}

# Create ZIP
Write-Host "📦 Creating portable ZIP..." -ForegroundColor Yellow
Compress-Archive -Path .\dist\PrismValidator\* -DestinationPath .\dist\PrismValidator-Portable.zip -Force
$zipSize = (Get-Item .\dist\PrismValidator-Portable.zip).Length / 1MB
Write-Host "   ZIP created: $($zipSize.ToString('F2')) MB" -ForegroundColor Green

# Test extraction
Write-Host "🧪 Testing ZIP extraction..." -ForegroundColor Yellow
$TestDir = "$env:TEMP\PrismValidator-Test"
Remove-Item -Recurse -Force $TestDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $TestDir -Force | Out-Null
Expand-Archive -Path .\dist\PrismValidator-Portable.zip -DestinationPath $TestDir -Force
Write-Host "   Extracted to: $TestDir" -ForegroundColor Cyan

# Launch test
Write-Host "🚀 Launching from extracted location..." -ForegroundColor Yellow
Write-Host "   Starting PrismValidator.exe..." -ForegroundColor Cyan
Start-Process -FilePath "$TestDir\PrismValidator.exe"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "✅ Build & Test Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "📂 Build location:    .\dist\PrismValidator\" -ForegroundColor Cyan
Write-Host "📦 ZIP location:      .\dist\PrismValidator-Portable.zip" -ForegroundColor Cyan
Write-Host "🧪 Test extraction:   $TestDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Application should open in browser at http://localhost:5001" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop PrismValidator process" -ForegroundColor Gray
```

---

## Manual Testing Checklist

After running the build, manually verify:

- [ ] Executable launches without errors
- [ ] Browser opens to `http://localhost:5001`
- [ ] Web interface loads correctly
- [ ] Can select demo dataset folder
- [ ] Validation completes successfully
- [ ] Can view validation report
- [ ] Can close application cleanly
- [ ] ZIP file is portable (test on different directory)
- [ ] No Python installation required to run
- [ ] No console window appears (GUI app)
- [ ] File size reasonable (~40-80 MB total, onefile build)
- [ ] Only 2 items in dist folder: `PrismValidator.exe` and `_internal/`

---

## Distribution

Once tested, distribute the ZIP file:

```powershell
# Copy ZIP to shared location
Copy-Item .\dist\PrismValidator-Portable.zip -Destination "\\NetworkShare\Software\PrismValidator.zip"

# Or create a GitHub release artifact
# (See RELEASE_GUIDE.md for GitHub Actions automation)
```

---

## Notes

- **VM Performance**: Build time depends on VM CPU cores and RAM allocation. Recommend at least 2 cores and 4GB RAM.
- **Antivirus**: Windows Defender may flag unsigned executables. See [WINDOWS_BUILD.md](WINDOWS_BUILD.md) for code signing options.
- **Updates**: Always clean build directory (`.\build` and `.\dist`) before creating release builds.
- **Version**: Version number is read from `app/src/__init__.py`

---

## Key Takeaways

### What Was Fixed
**Problem:** Users reported that the executable from GitHub releases would start (process appeared) but the browser wouldn't open, and nothing would happen.

**Root Cause:** PyInstaller was using the **root** `prism-studio.py` wrapper as the entry point, which expected an `app/` folder structure that doesn't exist in a frozen executable. This affected both local builds AND GitHub Actions builds.

**Solution:** Changed the default entry point in `scripts/build/build_app.py` from `prism-studio.py` to `app/prism-studio.py`, which:

1. Has proper logging configured for frozen apps (writes to `~/prism_studio.log`)
2. Handles `sys._MEIPASS` correctly for bundled resources
3. Doesn't rely on directory structure that won't exist in frozen executables

**Impact:** 
- ✅ Local builds: Now work correctly (your VM builds)
- ✅ GitHub Actions: Next release will work correctly
- ⚠️ Previous GitHub releases: Have this bug (users should use next release)

**Note:** The `PrismValidator.spec` file had the correct entry point, but PyInstaller was generating a new spec on-the-fly from `build_app.py`, ignoring the existing `.spec` file.

### Build Configuration
- **Entry Point:** `app/prism-studio.py` (not root `prism-studio.py`)
- **Mode:** `--onedir` (directory-based distribution)
- **Console:** `--windowed` (no console window, GUI only)
- **Bundled Data:** templates/, static/, schemas/, src/, official/, survey_library/

### Testing the Build
1. **Check process:** `Get-Process -Name "PrismValidator"`
2. **Check port:** `Get-NetTCPConnection -LocalPort 5001`
3. **Check log:** `Get-Content "$env:USERPROFILE\prism_studio.log"`
4. **Manual browser:** `Start-Process "http://localhost:5001"`

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `.\setup.ps1 -Build` | Setup environment + PyInstaller |
| `.\.venv\Scripts\Activate.ps1` | Activate virtual environment |
| `python scripts\build\build_app.py` | Build executable |
| `.\dist\PrismValidator\PrismValidator.exe` | Run executable |
| `Compress-Archive -Path .\dist\PrismValidator\* -DestinationPath .\dist\PrismValidator-Portable.zip` | Create ZIP |
| `Get-Process PrismValidator \| Stop-Process` | Kill running instances |
| `Remove-Item -Recurse .\build, .\dist` | Clean build artifacts |
