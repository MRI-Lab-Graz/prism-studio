# Windows Tests - Quick Reference

## Running Tests

```powershell
# All tests (PowerShell - recommended)
.\tests\run_windows_tests.ps1

# All tests (Python)
python tests/run_windows_tests.py

# Individual test
python tests/test_windows_paths.py
python tests/test_windows_web_uploads.py
python tests/test_windows_datasets.py
python tests/test_windows_compatibility.py
```

## Test Coverage Matrix

| Category | Feature | Test File | Status |
|----------|---------|-----------|--------|
| **Paths** | Drive letters (C:\, D:\) | test_windows_paths.py | ✅ |
| | UNC paths (\\\\server\\share) | test_windows_paths.py | ✅ |
| | Long paths (>260 chars) | test_windows_paths.py | ✅ |
| | Mixed separators (/ and \\) | test_windows_paths.py | ✅ |
| | Relative paths | test_windows_paths.py | ✅ |
| **Filenames** | Reserved names (CON, PRN, etc.) | test_windows_paths.py | ✅ |
| | Invalid chars (<>:"\|?*) | test_windows_paths.py | ✅ |
| | Trailing spaces/dots | test_windows_paths.py | ✅ |
| | Length limits (255 chars) | test_windows_paths.py | ✅ |
| **System Files** | Windows (Thumbs.db, Desktop.ini) | test_windows_paths.py | ✅ |
| | macOS (.DS_Store, etc.) | test_windows_paths.py | ✅ |
| | Filtering in datasets | test_windows_datasets.py | ✅ |
| **File I/O** | Unicode filenames | test_windows_paths.py | ✅ |
| | Line endings (CRLF vs LF) | test_windows_paths.py | ✅ |
| | Text encodings | test_windows_paths.py | ✅ |
| | File locking | test_windows_datasets.py | ✅ |
| | Read-only files | test_windows_datasets.py | ✅ |
| **Web Uploads** | Path normalization | test_windows_web_uploads.py | ✅ |
| | Large batches (5000+ files) | test_windows_web_uploads.py | ✅ |
| | Session management | test_windows_web_uploads.py | ✅ |
| | Security (path traversal) | test_windows_web_uploads.py | ✅ |
| **Datasets** | Case-insensitive validation | test_windows_datasets.py | ✅ |
| | .bidsignore support | test_windows_datasets.py | ✅ |
| | Cross-platform datasets | test_windows_datasets.py | ✅ |
| **Core** | Platform detection | test_windows_compatibility.py | ✅ |
| | Cross-platform utilities | test_windows_compatibility.py | ✅ |

## Expected Output

```
🪟 PRISM WINDOWS TEST SUITE
============================================================
Platform: win32
Python: 3.14.1

✅ PASS - Core Windows Compatibility
✅ PASS - Windows Path & Filename Handling  
✅ PASS - Windows Web Interface Uploads
✅ PASS - Windows Dataset Validation

Result: 4/4 test suites passed
🎉 All Windows test suites passed!
```

## Troubleshooting

### UTF-8 Encoding Errors
If you see `UnicodeEncodeError`:
```powershell
# Set console to UTF-8
chcp 65001
```

### Import Errors
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Permission Errors
```powershell
# Run as Administrator
# Or check antivirus software
```

### Long Path Issues
```powershell
# Enable long paths (requires admin)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# Restart required
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Windows Tests
  if: runner.os == 'Windows'
  run: python tests/run_windows_tests.py
```

## Test Statistics

- **Total Tests:** 45
- **Test Suites:** 4
- **Pass Rate:** 100%
- **Platform:** Windows 10+

## Documentation

- Full Guide: [docs/WINDOWS_TESTING.md](WINDOWS_TESTING.md)
- Summary: [docs/WINDOWS_TEST_SUMMARY.md](WINDOWS_TEST_SUMMARY.md)
- Setup: [docs/WINDOWS_SETUP.md](WINDOWS_SETUP.md)

## Key Files

```
tests/
├── test_windows_paths.py          # 17 tests - Path handling
├── test_windows_web_uploads.py    # 11 tests - Web uploads
├── test_windows_datasets.py       # 10 tests - Dataset validation
├── test_windows_compatibility.py  #  7 tests - Core compatibility
├── run_windows_tests.py           # Master runner (Python)
└── run_windows_tests.ps1          # Master runner (PowerShell)
```

## Quick Checks

```powershell
# Check Python version
python --version

# Check if venv is active
$env:VIRTUAL_ENV

# Check platform
python -c "import sys; print(sys.platform)"

# Test one feature
python -c "from cross_platform import normalize_path; print(normalize_path('C:\\test'))"
```

---

**Need Help?** See [WINDOWS_TESTING.md](WINDOWS_TESTING.md) for detailed information.
