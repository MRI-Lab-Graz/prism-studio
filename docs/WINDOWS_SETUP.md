# Windows Installation and Usage Guide

## Overview

PRISM offers two installation paths for Windows users:

| Feature | Pre-Built Version | Development Setup |
|---------|------------------|-------------------|
| **Target Users** | Regular users, data validators | Developers, contributors |
| **Python Required** | No | Yes (3.8+) |
| **Setup Time** | ~1 minute | ~5-10 minutes |
| **Dependencies** | None | Full dev environment |
| **Code Editing** | ❌ Not possible | ✅ Full access |
| **File Size** | ~300-500 MB | ~1-2 GB (with cache) |

---

## Option 1: Pre-Built Executable (For Regular Users)

### Prerequisites
- Windows 10/11
- ~500 MB free disk space
- No Python installation required

### Installation

1. **Download** the latest `PrismValidator.exe` from [GitHub Releases](https://github.com/MRI-Lab-Graz/prism-studio/releases)
2. **Extract** the folder to your preferred location (e.g., `C:\Program Files\Prism\`)
3. **Done!** You can now use the application

### Usage

Double-click `PrismValidator.exe` to open the web interface, or run from Command Prompt:

```bat
C:\Program Files\Prism\PrismValidator.exe "C:\path\to\your\dataset"
```

### Advantages
- ✅ No Python installation needed
- ✅ Single file to download and run
- ✅ Minimal disk space
- ✅ Works out of the box
- ✅ Ideal for end users

### Limitations
- ❌ Cannot modify the source code
- ❌ Cannot install additional packages
- ❌ Cannot contribute to development

### Antivirus / SmartScreen Warnings

If you encounter warnings from Windows Defender or antivirus software:

1. **Windows Defender**: Click "More info" and then "Run anyway"
2. **Norton/McAfee/etc**: Add the `PrismValidator.exe` folder to your antivirus exclusions
3. **Why?**: Standalone executables created with PyInstaller are sometimes flagged by heuristic scanners (pattern-based detection). PRISM is open-source—you can verify the code on [GitHub](https://github.com/MRI-Lab-Graz/prism-studio)

---

## Option 2: Development Installation (For Developers)

### Prerequisites

1. **Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)
   - **Important**: Check "Add Python to PATH" during installation
   - Verify: `python --version`

2. **Git** (optional, for cloning)
   - Download from [git-scm.com](https://git-scm.com/download/win)

### Installation

#### Method 1: PowerShell Setup Script (Recommended for Developers)

1. Open **PowerShell** in the project directory
2. Run the automated setup:

```powershell
.\setup.ps1 -Dev
```

This will:
- Check for and optionally install `uv` (fast Python package manager)
- Create a virtual environment in `.\.venv`
- Install core dependencies from `requirements.txt`
- Install development tools from `requirements-dev.txt`
- Install the project in editable (development) mode

**For building executables**, add the `-Build` flag:

```powershell
.\setup.ps1 -Dev -Build
```

#### Method 2: Manual Setup

If you prefer manual setup or the PowerShell script doesn't work:

```bat
# 1. Clone the repository
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
.venv\Scripts\activate

# 4. Install core dependencies
pip install -r requirements.txt

# 5. (Optional) Install development tools
pip install -r requirements-dev.txt

# 6. (Optional) Install build dependencies
pip install -r requirements-build.txt
```

### Requirements Files Explained

The project uses multiple requirements files for different use cases:

- **`requirements.txt`** – Core dependencies for running PRISM (installed with all methods)
- **`requirements-dev.txt`** – Development tools (testing, documentation, linting)
  - Installed with `.\setup.ps1 -Dev`
  - Includes: pytest, sphinx, black, flake8, etc.
- **`requirements-build.txt`** – Build tools for creating executables
  - Installed with `.\setup.ps1 -Build`
  - Includes: PyInstaller, etc.

### Activation

Always activate the virtual environment before using PRISM:

```bat
.venv\Scripts\activate
```

You'll see `(.venv)` at the start of your prompt when activated.

### Usage

Once activated:

```bat
# Validate a dataset
python prism.py "C:\Users\username\Documents\my_dataset"

# Run the web interface
python prism-studio.py

# Show help
python prism.py --help

# Run tests
python -m pytest tests\

# Run Windows compatibility tests
python tests\test_windows_compatibility.py
```

### Advantages
- ✅ Full source code access
- ✅ Can modify and extend functionality
- ✅ Includes testing and development tools
- ✅ Suitable for contributions
- ✅ Can build custom executables

### Limitations
- ❌ Requires Python installation
- ❌ Longer initial setup
- ❌ More disk space needed

---

## Windows-Specific Features (Both Installations)

### Cross-Platform Compatibility
The validator includes Windows-specific handling for:

- **File Paths**: Automatic normalization of path separators (`\` and `/`)
- **Line Endings**: Proper handling of CRLF (`\r\n`) line endings
- **Case Sensitivity**: Awareness of Windows' case-insensitive filesystem
- **Reserved Names**: Detection of Windows reserved filenames (CON, PRN, AUX, NUL, LPT*, COM*)
- **Filename Length**: Enforcement of Windows 255-character filename limit

### File Encoding
- All JSON files are read/written with UTF-8 encoding
- Automatic detection and handling of different line ending formats
- Support for Unicode characters in filenames and content

### Path Handling Examples

```bat
# All of these work correctly:
python prism.py "C:\Users\username\Documents\dataset"
python prism.py C:/Users/username/Documents/dataset
python prism.py "\\server\share\dataset"  # UNC paths

# Quotes are needed for paths with spaces:
python prism.py "C:\My Documents\My Dataset"
```

---

## Common Windows Issues and Solutions

### Issue: "Python is not recognized"

**Solution**: Python is not in your PATH. 

1. Reinstall Python
2. Check "Add Python to PATH" during installation
3. Restart PowerShell/Command Prompt
4. Verify with: `python --version`

### Issue: Long path names (>260 characters)

**Solution**: Enable long path support in Windows 10/11:

1. Run `gpedit.msc` as administrator
2. Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
3. Enable "Enable Win32 long paths"
4. Restart

### Issue: Antivirus/PowerShell blocks script execution

**Solution**: 

```powershell
# Allow scripts to run in current session only:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Virtual environment doesn't activate

**Solution**: Try using `activate.bat` instead of `.ps1`:

```bat
.venv\Scripts\activate.bat
```

### Issue: Pip installation fails

**Solutions**:
```bat
# Upgrade pip first
python -m pip install --upgrade pip

# Use alternative PyPI index if needed
pip install --index-url https://pypi.org/simple/ -r requirements.txt

# For corporate proxies
pip install --proxy [user:passwd@]proxy.server:port -r requirements.txt
```

### Issue: "ModuleNotFoundError: No module named 'prism'"

**Solution**: 

```bat
# Make sure you've activated the virtual environment:
.venv\Scripts\activate

# Reinstall editable mode:
pip install -e .
```

---

## File System Considerations

### Case Sensitivity

Windows filesystems are **case-insensitive**, meaning:
- `Subject-01` and `subject-01` are treated as the same file
- The validator will warn about potential conflicts
- **Best practice**: Be consistent with capitalization for cross-platform compatibility

### Reserved Characters

These characters **cannot** be used in Windows filenames:
- `< > : " | ? * \`
- Control characters (ASCII 0-31)

### Reserved Names

These names are **reserved** and cannot be used as filenames:
- `CON`, `PRN`, `AUX`, `NUL`
- `COM1` through `COM9`
- `LPT1` through `LPT9`

---

## Performance Tips

### Windows Defender
For better performance, exclude the project directory from Windows Defender real-time scanning:

1. Open Windows Security
2. Go to "Virus & threat protection"
3. Under "Virus & threat protection settings", click "Manage settings"
4. Scroll down and add your project folder under "Exclusions"

### SSD vs HDD
- Use an SSD for better I/O performance
- Network drives will be slower—validate on local storage if possible

---

## Troubleshooting Virtual Environment Issues

### Reset Virtual Environment

If you encounter strange errors, reset the environment:

```bat
# Remove environment
rmdir /s .venv

# Recreate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Building Executables for Distribution (Developers Only)

To create a standalone `PrismValidator.exe` for distribution:

```bat
# Activate environment
.venv\Scripts\activate

# Ensure build dependencies are installed
pip install -r requirements-build.txt

# Build the executable
pyinstaller --onedir --name PrismValidator --windowed prism-studio.py
```

The executable will be in `dist\PrismValidator\PrismValidator.exe`.

---

## Testing Windows Compatibility

Run the Windows compatibility test to diagnose environment issues:

```bat
python tests\test_windows_compatibility.py
```

This verifies:
- Platform detection
- Path handling
- Filename validation
- File operations
- Case sensitivity detection
- Module imports
- JSON handling with different encodings

---

## Getting Help

1. Check this guide for Windows-specific issues
2. Run `python tests\test_windows_compatibility.py` to identify environment problems
3. Check [INSTALLATION.md](INSTALLATION.md) for general setup
4. [Open an issue](https://github.com/MRI-Lab-Graz/prism-studio/issues) with:
   - Windows version (e.g., Windows 11 22H2)
   - Python version
   - Error messages
   - Output of the compatibility test

#### Issue: "Python is not recognized"
**Solution**: Python is not in your PATH. Reinstall Python and check "Add Python to PATH".

#### Issue: Long path names
**Solution**: Enable long path support in Windows 10/11:
1. Run `gpedit.msc` as administrator
2. Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
3. Enable "Enable Win32 long paths"

#### Issue: Antivirus (Defender, Norton, etc.) blocks the .exe
**Solution**: This is a common "False Positive" for unsigned Python-based executables.
1. **Windows Defender**: Click "More info" and then "Run anyway".
2. **Norton/Other AV**: If the file is deleted or blocked, you must go to your antivirus settings and "Restore" the file from quarantine or add an "Exclusion" for the `PrismValidator.exe` file.
3. **Why?**: Standalone `.exe` files created with PyInstaller are often flagged by heuristic scanners because they bundle a Python interpreter and many libraries into a single file, which is a pattern sometimes used by malware. Since PRISM is open-source, you can verify the code yourself.

#### Issue: Antivirus blocking script execution
**Solution**: Add the project folder to your antivirus exclusions.

#### Issue: PowerShell execution policy
**Solution**: If using PowerShell, you may need to run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Testing Windows Compatibility

Run the Windows compatibility test:
```bat
python tests\test_windows_compatibility.py
```

This test verifies:
- Platform detection
- Path handling
- Filename validation
- File operations
- Case sensitivity detection
- Module imports
- JSON handling with different encodings

## File System Considerations

### Case Sensitivity
Windows filesystems are typically case-insensitive, meaning:
- `Subject-01` and `subject-01` are treated as the same file
- The validator will warn about potential conflicts
- Be consistent with capitalization for cross-platform compatibility

### Path Length Limits
- Windows has a 260-character path length limit (unless long paths are enabled)
- The validator checks for paths that might exceed this limit
- Use shorter directory and filename structures if needed

### Reserved Characters
These characters cannot be used in Windows filenames:
- `< > : " | ? * \`
- Control characters (ASCII 0-31)

### Reserved Names
These names are reserved and cannot be used as filenames:
- `CON`, `PRN`, `AUX`, `NUL`
- `COM1` through `COM9`
- `LPT1` through `LPT9`

## Performance Tips

### Windows Defender
For better performance, consider excluding the project directory from Windows Defender real-time scanning:
1. Open Windows Security
2. Go to Virus & threat protection
3. Manage settings under "Virus & threat protection settings"
4. Add an exclusion for your project folder

### SSD vs HDD
- Use an SSD for better I/O performance when validating large datasets
- Consider the location of your dataset (local vs network drive)

## Troubleshooting

### Virtual Environment Issues
If you encounter virtual environment issues:
```bat
# Remove existing environment
rmdir /s .venv

# Recreate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Package Installation Issues
If pip installations fail:
```bat
# Upgrade pip
python -m pip install --upgrade pip

# Use alternate index if needed
pip install --index-url https://pypi.org/simple/ -r requirements.txt
```

### Network/Proxy Issues
If you're behind a corporate firewall:
```bat
# Set proxy (replace with your proxy details)
pip install --proxy https://user:password@proxy.server:port -r requirements.txt
```

## Building for Distribution

To create a standalone Windows executable:
```bat
# Install PyInstaller
pip install pyinstaller

# Create executable
pyinstaller --onefile prism.py
```

## Getting Help

1. Check this guide for Windows-specific issues
2. Run the compatibility test to identify problems
3. Check the main README.md for general usage
4. Report Windows-specific bugs with system information:
   - Windows version
   - Python version
   - Error messages
   - Output of `python tests\test_windows_compatibility.py`