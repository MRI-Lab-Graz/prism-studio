# Windows Installation and Usage Guide

This guide covers Windows-specific setup and usage for the prism.

## Prerequisites

### Python Installation
1. Download Python 3.8+ from [python.org](https://www.python.org/downloads/)
2. **Important**: Check "Add Python to PATH" during installation
3. Verify installation:
   ```bat
   python --version
   ```

### Git (Optional)
Install [Git for Windows](https://git-scm.com/download/win) if you want to clone the repository.

## Installation

### Method 1: Automatic Setup (Recommended)
1. Open Command Prompt or PowerShell
2. Navigate to the prism directory
3. Run the setup script:
   ```bat
   scripts\setup-windows.bat
   ```

### Method 2: Manual Setup
1. Open Command Prompt in the project directory
2. Create virtual environment:
   ```bat
   python -m venv .venv
   ```
3. Activate virtual environment:
   ```bat
   .venv\Scripts\activate
   ```
4. Install dependencies:
   ```bat
   pip install -r requirements.txt
   ```

## Usage

### Activating the Environment
Always activate the virtual environment before using the validator:
```bat
.venv\Scripts\activate
```

### Basic Validation
```bat
python prism.py "C:\path\to\your\dataset"
```

### Windows-Specific Path Handling
- Use either forward slashes `/` or backslashes `\` in paths
- Quote paths containing spaces: `"C:\My Documents\dataset"`
- UNC paths are supported: `\\server\share\dataset`

### Example Commands
```bat
# Validate a local dataset
python prism.py "C:\Users\username\Documents\my_dataset"

# Validate with verbose output
python prism.py --verbose "D:\research\experiment_data"

# Show help
python prism.py --help

# Run tests
python -m pytest tests\
```

## Windows-Specific Features

### Cross-Platform Compatibility
The validator includes Windows-specific handling for:
- **File Paths**: Automatic normalization of path separators
- **Line Endings**: Proper handling of CRLF (`\r\n`) line endings
- **Case Sensitivity**: Awareness of Windows' case-insensitive filesystem
- **Reserved Names**: Detection of Windows reserved filenames (CON, PRN, AUX, etc.)
- **Filename Length**: Enforcement of Windows 255-character filename limit

### File Encoding
- All JSON files are read/written with UTF-8 encoding
- Automatic detection and handling of different line ending formats
- Support for Unicode characters in filenames and content

### Common Windows Issues and Solutions

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