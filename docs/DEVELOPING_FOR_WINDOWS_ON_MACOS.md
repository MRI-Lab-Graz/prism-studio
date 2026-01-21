# Developing for Windows Users on macOS

This guide helps you develop and test PRISM for Windows users while working on macOS.

## The Challenge

Your main users are on Windows, but you develop on macOS. This can lead to platform-specific issues that aren't caught during development. This guide provides strategies to minimize these issues.

## 1. Virtual Machine / Parallels Desktop

### Option A: Free - UTM (QEMU)
```bash
# Install UTM
brew install --cask utm

# Download Windows 11 ARM ISO from Microsoft
# Create a new VM in UTM
# Install Windows
```

**Pros**: Free, runs on Apple Silicon
**Cons**: Slower than native, requires Windows license

### Option B: Paid - Parallels Desktop (~$100/year)
```bash
brew install --cask parallels
```

**Pros**: Fast, seamless integration with macOS, easy file sharing
**Cons**: Costs money, requires Windows license

### Testing Workflow with VM:
1. Share your project folder between macOS and Windows VM
2. Develop on macOS as usual
3. Test on Windows VM:
   ```powershell
   cd Z:\path\to\psycho-validator  # Shared drive
   .\setup.ps1
   python prism-studio.py
   ```

## 2. GitHub Actions for Automated Testing

Already set up! Every push/PR automatically tests on Windows.

**Check build status**: Look at GitHub Actions tab in your repo

To test locally before pushing:
```bash
git add .
git commit -m "Test Windows changes"
git push origin branch-name
# Check Actions tab on GitHub
```

## 3. Cross-Platform Development Best Practices

### Use Path Utilities Everywhere
```python
# ✅ Good - works on all platforms
from pathlib import Path
path = base_dir / "subfolder" / "file.json"

# ✅ Also good
import os
path = os.path.join(base_dir, "subfolder", "file.json")

# ❌ Bad - won't work on Windows
path = base_dir + "/subfolder/file.json"
```

### Test Path Separators
```python
# Test that your code handles both
test_path_unix = "/Users/karl/work/dataset"
test_path_windows = "C:\\Users\\Karl\\Documents\\dataset"
```

### Subprocess Commands
```python
# ✅ Good - cross-platform
subprocess.run(["command", "arg1", "arg2"])

# ❌ Bad - Unix-specific
subprocess.run("command arg1 arg2", shell=True)
```

### Check Platform When Needed
```python
import sys

if sys.platform.startswith('win'):
    # Windows-specific code
elif sys.platform == 'darwin':
    # macOS-specific code
else:
    # Linux-specific code
```

## 4. Manual Testing Checklist (When You Have Access to Windows)

Create `test_windows.md` with these checks:

- [ ] **Setup**: Run `setup.ps1` - no errors?
- [ ] **Startup**: Run `prism-studio.py` - browser opens?
- [ ] **Folder Picker**: Click browse buttons - native dialog appears?
- [ ] **Path Entry**: Enter Windows paths manually - validation works?
- [ ] **File Upload**: Drag folder into browser - works?
- [ ] **Validation**: Validate a dataset - results show correctly?
- [ ] **Export**: Download report - file downloads?
- [ ] **Compiled Version**: Run `.exe` - everything works?

## 5. Common Windows-Specific Issues to Watch For

### Issue: Paths with Backslashes
**Solution**: Always normalize paths
```python
path = path.replace("\\", "/")  # For display
# Or use pathlib.Path() which handles it automatically
```

### Issue: Line Endings (CRLF vs LF)
**Solution**: Configure git to handle it
```bash
# In .gitattributes (already set up)
* text=auto
*.py text eol=lf
*.sh text eol=lf
*.ps1 text eol=crlf
```

### Issue: Case-Insensitive Filesystem
**Solution**: Test with case variations
```python
# Windows treats these as the same:
Path("Dataset_Description.json")
Path("dataset_description.json")
```

### Issue: Console Apps vs GUI Apps
**Solution**: 
- Development: Keep `console=True` in PyInstaller for debugging
- Production: Use `console=False` but add logging (already implemented)

### Issue: tkinter Not Available
**Solution**: Already handled - graceful fallback with error message

## 6. Log Files for Debugging

When Windows users report issues:

1. Ask them to check the log file:
   ```
   C:\Users\<username>\prism_studio.log
   ```

2. The log contains all stdout/stderr output

3. Ask them to share the log file with you

## 7. Remote Testing Services (Optional)

If you need quick Windows testing without a VM:

- **BrowserStack** - Test in real Windows browsers (paid)
- **GitHub Codespaces** - Spin up Windows environment in browser
- **Azure Lab Services** - Free for students/educators

## 8. Pre-Release Windows Testing Protocol

Before releasing a new version:

1. **Test on GitHub Actions**: Ensure all tests pass on Windows
2. **Build Windows executable**: Run build on Windows VM or use GitHub Actions
3. **Test executable**: 
   - Run on clean Windows VM
   - Test folder picker
   - Test file uploads
   - Test validation
4. **Check log file**: Ensure no unexpected errors
5. **Test with real user data**: Use typical Windows paths
6. **Document Windows-specific notes** in release notes

## 9. Quick Windows Testing Script

Save as `scripts/test_windows_compat.py`:

```python
#!/usr/bin/env python3
"""Quick test for Windows compatibility issues."""
import sys
import os
from pathlib import Path

def test_windows_paths():
    """Test Windows path handling."""
    test_paths = [
        "C:\\Users\\Test\\Documents\\dataset",
        "C:/Users/Test/Documents/dataset",
        "\\\\network\\share\\dataset",
    ]
    
    print("Testing Windows path handling...")
    for path in test_paths:
        try:
            # Normalize and test
            normalized = Path(path)
            print(f"✅ {path} → {normalized}")
        except Exception as e:
            print(f"❌ {path} → ERROR: {e}")

def test_subprocess_commands():
    """Test subprocess calls work on Windows."""
    commands = [
        ["python", "--version"],
        ["where" if sys.platform.startswith('win') else "which", "python"],
    ]
    
    print("\nTesting subprocess commands...")
    for cmd in commands:
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"✅ {' '.join(cmd)}")
        except Exception as e:
            print(f"❌ {' '.join(cmd)} → ERROR: {e}")

if __name__ == "__main__":
    test_windows_paths()
    test_subprocess_commands()
    
    print("\n" + "="*50)
    print("Platform:", sys.platform)
    print("Python:", sys.version)
    print("="*50)
```

Run with: `python scripts/test_windows_compat.py`

## 10. Getting Help from Windows Users

When asking Windows users to test:

**Provide clear instructions:**
```
1. Download: [link to release]
2. Extract to: C:\PRISM
3. Double-click PrismValidator.exe
4. If nothing happens, check: C:\Users\YourName\prism_studio.log
5. Share the log file with me
```

**Use screenshare/video**: Ask users to record a quick video if issues persist

## Summary

**Essential**:
- ✅ Use `pathlib.Path()` or `os.path.join()` everywhere
- ✅ Test subprocess calls with list format
- ✅ Check GitHub Actions for Windows tests
- ✅ Handle Windows paths in error messages

**Nice to Have**:
- Virtual machine for hands-on testing
- Pre-release testing checklist
- Log files from real Windows users

**Remember**:
- Most Windows-specific issues are path-related
- The code is already cross-platform compatible
- GitHub Actions catches most issues automatically
- Log files help debug user-reported issues

Your code is already quite Windows-compatible! The recent fixes (tkinter checks, better browser launching, logging) address the main remaining issues.
