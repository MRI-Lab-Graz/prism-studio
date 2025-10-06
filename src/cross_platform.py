"""
Cross-platform compatibility utilities for psycho-validator
"""

import os
import sys
from pathlib import Path, PurePath


def normalize_path(path):
    """Normalize path separators for cross-platform compatibility"""
    return str(Path(path).as_posix()) if path else path


def safe_path_join(*args):
    """Safe path joining that works across platforms"""
    return str(Path(*args))


def get_platform_info():
    """Get platform-specific information"""
    return {
        'platform': sys.platform,
        'is_windows': sys.platform.startswith('win'),
        'is_posix': os.name == 'posix',
        'path_separator': os.sep,
        'line_separator': os.linesep
    }


def normalize_line_endings(text):
    """Normalize line endings for cross-platform compatibility"""
    # Convert to Unix-style line endings, then to platform-appropriate
    return text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', os.linesep)


def get_executable_extension():
    """Get the appropriate executable extension for the platform"""
    return '.exe' if sys.platform.startswith('win') else ''


def case_insensitive_glob(pattern, path='.'):
    """Case-insensitive file globbing for Windows compatibility"""
    from pathlib import Path
    import fnmatch
    
    path_obj = Path(path)
    if not path_obj.exists():
        return []
    
    # On Windows, filesystem is case-insensitive anyway
    # On Unix, we need to do case-insensitive matching manually
    if sys.platform.startswith('win'):
        return list(path_obj.glob(pattern))
    else:
        # Manual case-insensitive matching for Unix systems
        results = []
        for item in path_obj.rglob('*'):
            if fnmatch.fnmatch(item.name.lower(), pattern.lower()):
                results.append(item)
        return results


class CrossPlatformFile:
    """File operations that work consistently across platforms"""
    
    @staticmethod
    def read_text(filepath, encoding='utf-8'):
        """Read text file with proper encoding handling"""
        try:
            # Try UTF-8 first (most common)
            with open(filepath, 'r', encoding=encoding, newline='') as f:
                content = f.read()
            return normalize_line_endings(content)
        except UnicodeDecodeError:
            # Fallback to system default encoding
            with open(filepath, 'r', encoding=sys.getdefaultencoding(), newline='') as f:
                content = f.read()
            return normalize_line_endings(content)
    
    @staticmethod
    def write_text(filepath, content, encoding='utf-8'):
        """Write text file with proper encoding"""
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding=encoding, newline='') as f:
            f.write(content)


def get_temp_dir():
    """Get platform-appropriate temporary directory"""
    import tempfile
    return tempfile.gettempdir()


def is_case_sensitive_filesystem(path='.'):
    """Check if the filesystem is case-sensitive"""
    import tempfile
    import os
    
    # Create a temporary file with lowercase name
    with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=path, suffix='.tmp') as f:
        temp_path = f.name
        f.write('test')
    
    try:
        # Try to access it with uppercase name
        uppercase_path = temp_path.replace(temp_path[-8:-4], temp_path[-8:-4].upper())
        case_sensitive = not os.path.exists(uppercase_path)
        return case_sensitive
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def validate_filename_cross_platform(filename):
    """Validate filename for cross-platform compatibility"""
    issues = []
    
    # Windows filename restrictions
    if sys.platform.startswith('win'):
        # Reserved names in Windows
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            issues.append(f"Filename '{filename}' uses Windows reserved name")
        
        # Invalid characters in Windows
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            if char in filename:
                issues.append(f"Filename '{filename}' contains invalid character '{char}' for Windows")
        
        # Trailing spaces or dots
        if filename.endswith(' ') or filename.endswith('.'):
            issues.append(f"Filename '{filename}' ends with space or dot (invalid on Windows)")
    
    # General cross-platform issues
    if len(filename) > 255:
        issues.append(f"Filename '{filename}' too long (>255 characters)")
    
    return issues