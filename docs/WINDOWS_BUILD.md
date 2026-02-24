# Building and Signing Prism Validator on Windows

This guide explains how to build the Prism Validator Windows application from source and sign it for distribution to IT departments.

## Prerequisites

1. **Python 3.8 or higher** installed on your system
   - Download from: https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation

2. **Git** (if cloning the repository)
   - Download from: https://git-scm.com/download/win

## Code Signing for IT Departments

IT departments often require signed executables. Here's how to sign your Windows build **for free** (for open source projects):

### Option 1: SignPath.io (Recommended - FREE for Open Source)

SignPath provides **free code signing** for open source projects and integrates with GitHub Actions.

#### Setup Steps:

1. **Apply for Free OSS Signing**:
   - Go to: https://about.signpath.io/product/open-source
   - Fill out application with your GitHub repo URL
   - Approval usually takes 1-2 business days
   - You'll receive an organization ID and API token

2. **Add Secrets to GitHub**:
   ```
   Repository Settings → Secrets and variables → Actions → New repository secret
   ```
   Add:
   - `SIGNPATH_API_TOKEN`: Your API token from SignPath
   - `SIGNPATH_ORGANIZATION_ID`: Your organization ID from SignPath

3. **The Workflow Automatically Signs**:
   - Already configured in `.github/workflows/build.yml`
   - Signing happens automatically when you create a release tag
   - Only signs if secrets are present (gracefully skips if not)

4. **Create a Release**:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```
   
   The signed executable will be in the GitHub release artifacts.

#### What Gets Signed:
- ✅ `PrismValidator.exe` - Main executable
- ✅ Certificate chain validates to trusted root
- ✅ SmartScreen won't block (after reputation builds)
- ✅ IT departments can verify signature

### Option 2: Self-Signed Certificate (FREE but LIMITED)

**Pros**: Completely free, can do locally
**Cons**: Windows SmartScreen will still warn, IT departments may not accept

Only use if SignPath doesn't work for your needs.

#### Create Self-Signed Certificate:

```powershell
# Run PowerShell as Administrator
$cert = New-SelfSignedCertificate `
    -Type Custom `
    -Subject "CN=PRISM Validator, O=MRI Lab Graz, C=AT" `
    -KeyUsage DigitalSignature `
    -FriendlyName "PRISM Validator Code Signing" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")

# Export certificate
$password = ConvertTo-SecureString -String "YourPassword" -Force -AsPlainText
Export-PfxCertificate `
    -Cert "Cert:\CurrentUser\My\$($cert.Thumbprint)" `
    -FilePath "PrismValidator-CodeSigning.pfx" `
    -Password $password
```

#### Sign the Executable:

```powershell
# After building with PyInstaller
signtool sign /f "PrismValidator-CodeSigning.pfx" /p "YourPassword" /t http://timestamp.digicert.com "dist\PrismValidator\PrismValidator.exe"
```

**Note**: You'll need to distribute the certificate to IT departments who will need to manually trust it.

### Option 3: Submit to Microsoft for SmartScreen Reputation

Even with a valid signature, Windows SmartScreen may warn until your app builds reputation:

1. **Sign with SignPath** (or paid certificate)
2. **Submit to Microsoft**:
   - Go to: https://www.microsoft.com/en-us/wdsi/filesubmission
   - Upload your signed executable
   - Request reputation review
3. **Build Reputation**:
   - Downloads from many users over time
   - SmartScreen warnings decrease automatically

### Verifying the Signature

After signing, verify it works:

```powershell
# Check signature
Get-AuthenticodeSignature "dist\PrismValidator\PrismValidator.exe"

# Should show:
# Status: Valid
# SignerCertificate: [Your certificate]
```

**CI verification:** The GitHub Actions build now runs a `Verify Windows Signature` step after SignPath signing that uses `Get-AuthenticodeSignature` to ensure the signature is valid. If the signature is invalid the Windows build will fail and you can inspect the job logs for the verification output.

In Windows Explorer:
1. Right-click the `.exe` file
2. Properties → Digital Signatures tab
3. Should show valid signature

## Quick Start (Building)

### Option 1: Using PowerShell (Recommended)

1. **Setup the environment:**
   Open PowerShell in the project directory and run:
   ```powershell
   .\setup.ps1 -Build
   ```

2. **Build the application:**
   ```powershell
   .\scripts\build\build_windows.ps1
   ```

### Option 2: Using Command Prompt

Open Command Prompt in the project directory and run:

```batch
build_windows.bat
```

### Option 3: Manual Build

If the automated scripts don't work, follow these steps:

1. **Create virtual environment:**
   ```batch
   python -m venv .venv
   ```

2. **Activate virtual environment:**
   ```batch
   .venv\Scripts\activate.bat
   ```

3. **Install dependencies:**
   ```batch
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-build.txt
   ```

4. **Create survey_library folder (optional but recommended):**
   ```batch
   mkdir survey_library
   ```

5. **Build the application:**
   ```batch
   python scripts\build\build_app.py
   ```

## Output

After a successful build, you'll find the application in:
```
dist\PrismValidator\PrismValidator.exe
```

You can:
- Run it directly: `dist\PrismValidator\PrismValidator.exe`
- Double-click `PrismValidator.exe` in Windows Explorer
- Copy the entire `dist\PrismValidator\` folder to another location

## Troubleshooting

### "Python not found"
- Make sure Python is installed and added to your PATH
- Try using `py` instead of `python`: `py -3 -m venv .venv`

### "Failed to create virtual environment"
- Make sure you have write permissions in the project directory
- Try running PowerShell or Command Prompt as Administrator

### "PyInstaller build fails"
- Make sure all dependencies are installed: `pip install -r requirements-build.txt`
- Check if antivirus software is blocking PyInstaller
- Try running with `--debug` flag: `python scripts\\build\\build_app.py --debug`

### Missing icon
- The build script will automatically use the PNG logo from `static/img/MRI_Lab_Logo.png`
- If the file is missing, the build will continue without an icon

### survey_library warnings
- The `survey_library` folder is optional
- If you see a warning, the build will continue normally
- The folder is only needed if you use the survey management features

## Building for Distribution

The built application in `dist\PrismValidator\` includes:
- `PrismValidator.exe` - Main executable
- `_internal\` - Required libraries and data files
- All templates, static files, and schemas

To distribute:
1. Compress the entire `dist\PrismValidator\` folder to a ZIP file
2. Share the ZIP file with end users
3. Users can extract and run `PrismValidator.exe` without installing Python

## Platform-Specific Notes

- The Windows build uses a **folder-based distribution** (`--onedir`)
- All dependencies are packaged in the `_internal` folder
- The application runs **without a console window** (`--windowed`)
- Icon support requires a PNG or ICO file (automatically handled)

## Next Steps

After building:
- Test the application: `cd dist\PrismValidator && .\PrismValidator.exe`
- The web interface will start on `http://localhost:5001`
- Check the logs if the application doesn't start

## See Also

- [General Installation Guide](INSTALLATION.md)
- [Windows Setup Guide](WINDOWS_SETUP.md)
- [Windows Setup Guide](WINDOWS_SETUP.md)
