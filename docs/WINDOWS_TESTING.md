# Windows Testing Guide

This guide describes the Windows-specific tests for the PRISM validator and how to run them.

## Overview

Since PRISM was originally developed on macOS, comprehensive Windows testing is essential to ensure cross-platform compatibility. The Windows test suite covers:

- Path handling (backslashes, drive letters, UNC paths)
- Filename validation (reserved names, invalid characters)
- System file filtering (Thumbs.db, Desktop.ini, etc.)
- File I/O operations (line endings, encodings, Unicode)
- Web upload functionality
- Dataset validation on Windows filesystems

## Test Files

### 1. `test_windows_compatibility.py`
**Core Windows Compatibility Tests**

Tests basic cross-platform utilities:
- Platform detection
- Path normalization
- Filename validation
- Case sensitivity detection
- JSON handling with various encodings

**Run:**
```powershell
python tests/test_windows_compatibility.py
```

### 2. `test_windows_paths.py`
**Windows Path & Filename Handling**

Comprehensive tests for Windows-specific path scenarios:
- Drive letters (C:\, D:\, etc.)
- UNC network paths (\\server\share)
- Long paths (>260 characters)
- Mixed path separators (/, \)
- Relative paths with backslashes
- Reserved filenames (CON, PRN, AUX, etc.)
- Invalid characters (<, >, :, ", |, ?, *)
- Trailing spaces and dots
- Filename length limits

**Run:**
```powershell
python tests/test_windows_paths.py
```

### 3. `test_windows_web_uploads.py`
**Windows Web Interface Upload Tests**

Tests web upload functionality with Windows considerations:
- Upload path normalization
- Drive letter handling in paths
- Large batch uploads (5000+ files)
- DataLad-style uploads (metadata only)
- Session directory management
- Temporary file cleanup
- Concurrent session isolation
- Path traversal prevention
- Filename injection prevention

**Run:**
```powershell
python tests/test_windows_web_uploads.py
```

### 4. `test_windows_datasets.py`
**Windows Dataset Validation Tests**

Tests PRISM dataset validation on Windows:
- Case-insensitive filesystem behavior
- Mixed case subject folders
- Windows path validation
- System file filtering in datasets
- Locked file handling
- Long filename paths
- Read-only file handling
- .bidsignore with Windows paths
- Cross-platform dataset compatibility

**Run:**
```powershell
python tests/test_windows_datasets.py
```

## Running All Tests

### Quick Run
```powershell
python tests/run_windows_tests.py
```

This will run all four test suites sequentially and provide a summary.

### Individual Test Runs
```powershell
# Core compatibility
python tests/test_windows_compatibility.py

# Path handling
python tests/test_windows_paths.py

# Web uploads
python tests/test_windows_web_uploads.py

# Dataset validation
python tests/test_windows_datasets.py
```

### Within Virtual Environment
```powershell
# Activate virtual environment first
.\.venv\Scripts\Activate.ps1

# Then run tests
python tests/run_windows_tests.py
```

## Test Output

Each test provides detailed output:
- ✅ Test passed
- ❌ Test failed
- ⚠️ Warning (non-critical issue or platform-specific note)
- ℹ️ Information

Example output:
```
🧪 Testing drive letters...
  ✅ C:\Users\test\dataset -> C:/Users/test/dataset
  ✅ D:\data\prism -> D:/data/prism
  
🧪 Testing reserved filenames...
  ✅ Detected: CON.json - Filename 'CON.json' uses Windows reserved name
  ✅ Detected: PRN.tsv - Filename 'PRN.tsv' uses Windows reserved name
```

## Windows-Specific Considerations

### Case Sensitivity
Windows filesystems (NTFS, FAT32) are case-insensitive but case-preserving:
- `Sub-01` and `sub-01` refer to the same directory
- PRISM normalizes to lowercase for consistency
- Tests verify proper handling

### Path Separators
Windows uses backslashes (`\`) but Python/PRISM normalizes to forward slashes (`/`):
- Input: `C:\Users\test\dataset`
- Normalized: `C:/Users/test/dataset`

### Reserved Names
Windows reserves certain names that cannot be used as filenames:
- Device names: `CON`, `PRN`, `AUX`, `NUL`
- Serial ports: `COM1`-`COM9`
- Parallel ports: `LPT1`-`LPT9`

Tests verify these are properly detected and rejected.

### Invalid Characters
Windows does not allow these characters in filenames:
- `< > : " | ? *`
- Trailing spaces or dots

Tests verify proper validation.

### Long Paths
Traditional Windows has a 260-character path limit. Modern Windows 10+ can support longer paths if enabled:
```powershell
# Enable long paths (requires admin)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

Tests verify behavior with and without long path support.

### System Files
Windows-specific system files that should be ignored:
- `Thumbs.db` - Thumbnail cache
- `ehthumbs.db` - Enhanced thumbnails
- `Desktop.ini` - Folder settings
- `$RECYCLE.BIN` - Recycle bin
- `System Volume Information` - System restore

### Line Endings
Windows uses CRLF (`\r\n`), while Unix uses LF (`\n`). PRISM normalizes line endings for cross-platform compatibility.

## Common Issues

### Test Failures on Non-Windows Platforms

If running these tests on macOS/Linux:
```
⚠️ Warning: Not running on Windows!
Some tests may behave differently on non-Windows platforms.
```

This is expected. Some tests will pass with warnings, others may fail due to platform differences (e.g., case sensitivity, reserved names).

### Permission Errors

If tests fail with permission errors:
```powershell
# Run PowerShell as Administrator
# Or check antivirus software isn't blocking file operations
```

### Import Errors

If you see import errors:
```powershell
# Ensure you're in the correct directory
cd c:\Users\karl\github\prism-validator

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Long Path Issues

If tests fail due to path length:
```powershell
# Check if long paths are enabled
Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled"

# Enable if needed (requires admin)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## Continuous Integration

For CI/CD pipelines on Windows:

```yaml
# GitHub Actions example
- name: Run Windows Tests
  if: runner.os == 'Windows'
  run: |
    python tests/run_windows_tests.py
```

## Contributing

When adding new Windows-specific tests:

1. Add tests to the appropriate file or create a new one
2. Follow existing test structure (test classes with `test_*` methods)
3. Include descriptive print statements for test progress
4. Handle non-Windows platforms gracefully (warnings, not failures)
5. Update this documentation

## Related Documentation

- [Windows Setup Guide](WINDOWS_SETUP.md)
- [Windows Build Guide](WINDOWS_BUILD.md)
- [Cross-Platform Compatibility](../app/src/cross_platform.py)
- [System File Filtering](../app/src/system_files.py)

## Support

For Windows-specific issues:
1. Check the test output for specific error messages
2. Review [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for configuration
3. Check GitHub Issues for similar problems
4. Create a new issue with:
   - Windows version
   - Python version
   - Full test output
   - Error messages
