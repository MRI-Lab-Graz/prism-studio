# Cross-Platform Compatibility

PRISM Studio is designed to work seamlessly across macOS, Windows, and Linux. This document outlines the platform-specific features and compatibility measures.

## Platform Support

### Operating Systems
- **macOS** 10.15+ (Catalina and later)
- **Windows** 10/11
- **Linux** (Ubuntu 20.04+, Debian, Fedora, other distributions)

### Web Interface Browser Compatibility

#### Folder Upload (webkitdirectory)
- **Windows**: Chrome 21+, Edge 79+, Firefox 50+
- **macOS**: Safari 11.1+, Chrome 21+, Firefox 50+
- **Linux**: Chrome 21+, Firefox 50+

The web interface automatically detects browser capabilities and shows appropriate warnings if folder upload is not supported.

## Native Folder Picker

The `/api/browse-folder` endpoint provides a native OS dialog for selecting folders:

### macOS
- Uses AppleScript via `osascript`
- Provides native macOS folder picker dialog
- No additional dependencies required

### Windows
- Uses `tkinter.filedialog.askdirectory`
- Provides native Windows folder picker dialog
- Requires tkinter (included with standard Python installation on Windows)

### Linux
- Uses `tkinter.filedialog.askdirectory`
- Requires X11/Wayland display session
- Returns 501 error on headless servers (manual path entry fallback)
- Requires `python3-tk` package on some distributions:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install python3-tk
  
  # Fedora
  sudo dnf install python3-tkinter
  ```

### Fallback Behavior
If the native picker fails or is unavailable:
- User can manually enter the path in the text field
- Error message displays: "Folder picker not available. Please enter path manually."

## Path Handling

### Path Separators
All path manipulation uses platform-agnostic methods:
- **Python**: `os.path.join()`, `pathlib.Path()` with `/` operator
- **JavaScript**: Normalized to forward slashes for consistency
- Automatic conversion: `path.replace("\\", "/")` for display

### Temporary Directories
Platform-specific temp directories are handled automatically:
- **macOS**: `/var/folders/.../T/prism_validator_*`
- **Windows**: `C:\Users\...\AppData\Local\Temp\prism_validator_*`
- **Linux**: `/tmp/prism_validator_*`

Path cleaning in error messages recognizes all patterns.

### File System Case Sensitivity
- **Windows**: Case-insensitive (default)
- **macOS**: Case-insensitive by default (APFS/HFS+), can be case-sensitive
- **Linux**: Case-sensitive

PRISM handles this automatically, but datasets should use consistent casing for maximum portability.

## Subprocess Calls

All subprocess calls use secure, cross-platform patterns:
```python
# ✅ Correct - works on all platforms
subprocess.run(["command", "arg1", "arg2"], ...)

# ❌ Avoided - platform-specific
subprocess.run("command arg1 arg2", shell=True)
```

### External Tools
- **BIDS Validator**: Uses `deno` or `bids-validator` (both cross-platform)
- **Python**: Uses `sys.executable` for invoking Python scripts
- All commands use list format (not shell strings)

## Known Limitations

### Linux Headless Environments
- Native folder picker requires desktop session
- SSH without X11 forwarding: manual path entry only
- Workaround: Use command-line validator or setup X11 forwarding

### Windows Path Length
- Windows has a 260-character path limit (legacy `MAX_PATH`)
- Enable long path support in Windows 10 1607+:
  ```
  Computer Configuration > Administrative Templates > System > Filesystem > Enable Win32 long paths
  ```
- Or use Python 3.6+ which handles long paths automatically with UNC prefix

### macOS Gatekeeper
- Downloaded apps may be blocked by Gatekeeper
- Solution: System Preferences > Security & Privacy > "Open Anyway"

## Testing Checklist

When developing cross-platform features:

- [ ] Test path handling with both `/` and `\` separators
- [ ] Test temp directory creation/cleanup on each platform
- [ ] Verify subprocess calls work without `shell=True`
- [ ] Check file uploads with various path structures
- [ ] Test native folder picker dialogs
- [ ] Verify error messages don't expose platform-specific paths
- [ ] Test with case-sensitive and case-insensitive filesystems
- [ ] Verify long paths work on Windows

## Development Notes

### Path Construction
```python
# ✅ Correct
from pathlib import Path
path = base_dir / "subfolder" / "file.json"

# ✅ Also correct
path = os.path.join(base_dir, "subfolder", "file.json")

# ❌ Avoid
path = base_dir + "/subfolder/file.json"  # Won't work on Windows
```

### Path Display
```python
# Always normalize for display
display_path = file_path.replace("\\", "/")
```

### Checking Platform
```python
import sys

if sys.platform == "darwin":
    # macOS-specific code
elif sys.platform.startswith("win"):
    # Windows-specific code
else:
    # Linux/Unix-specific code
```

## Troubleshooting

### Windows: "Folder picker not available"
- Ensure Python includes tkinter: `python -m tkinter`
- Reinstall Python with "tcl/tk and IDLE" option

### Linux: "Folder picker requires a desktop session"
- Running on server without GUI
- Solution: Enter path manually or use CLI validator

### macOS: AppleScript permission denied
- Grant Terminal/Python access to Automation in System Preferences > Security & Privacy

### Path not found errors
- Check for extra quotes or spaces in paths
- On Windows, use either forward slashes or double backslashes
  - OK: `C:/Users/name/dataset`
  - OK: `C:\\Users\\name\\dataset`
  - NOT OK: `C:\Users\name\dataset` (escapes get interpreted)

## Contributing

When adding new features, always:
1. Use `pathlib.Path` or `os.path` for file operations
2. Test on at least two different platforms
3. Avoid hardcoded path separators in strings
4. Use platform checks (`sys.platform`) only when absolutely necessary
5. Document any platform-specific behavior
