"""
System file filtering utilities for cross-platform dataset validation.
Filters out OS-specific files that shouldn't be included in validation.
"""

import os

# System files to ignore during validation
SYSTEM_FILES = {
    # macOS system files
    '.DS_Store',           # Finder metadata
    '._.DS_Store',         # macOS resource fork
    '._*',                 # macOS AppleDouble files (pattern)
    '.Spotlight-V100',     # Spotlight search index
    '.Trashes',           # Trash folder
    '.fseventsd',         # File system events daemon
    '.VolumeIcon.icns',   # Volume icon
    
    # Windows system files
    'Thumbs.db',          # Windows thumbnail cache
    'ehthumbs.db',        # Windows thumbnail cache
    'Desktop.ini',        # Windows folder settings
    '$RECYCLE.BIN',       # Windows recycle bin
    'System Volume Information',  # Windows system folder
    
    # Linux/Unix system files
    '.directory',         # KDE folder settings
    '.hidden',           # Hidden file list
    
    # Version control and IDE files
    '.git',              # Git repository
    '.gitignore',        # Git ignore file
    '.svn',              # Subversion
    '.hg',               # Mercurial
    '.idea',             # IntelliJ IDEA
    '.vscode',           # Visual Studio Code
    '__pycache__',       # Python cache
    '*.pyc',             # Python bytecode (pattern)
    '.pytest_cache',     # Pytest cache
    
    # Temporary files
    '.tmp',              # Temporary files
    '~*',                # Backup files (pattern)
    '#*#',               # Emacs temp files (pattern)
    '.#*',               # Emacs lock files (pattern)
}

# Patterns that need special matching (contain wildcards)
SYSTEM_FILE_PATTERNS = {
    '._*',      # macOS AppleDouble files
    '*.pyc',    # Python bytecode
    '~*',       # Backup files
    '#*#',      # Emacs temp files
    '.#*',      # Emacs lock files
}


def is_system_file(filename):
    """
    Check if a filename is a system file that should be ignored during validation.
    
    Args:
        filename (str): The filename to check
        
    Returns:
        bool: True if the file should be ignored, False otherwise
    """
    if not filename:
        return True
        
    # Check exact matches
    if filename in SYSTEM_FILES:
        return True
        
    # Check patterns
    import fnmatch
    for pattern in SYSTEM_FILE_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return True
            
    return False


def filter_system_files(file_list):
    """
    Filter out system files from a list of filenames.
    
    Args:
        file_list (list): List of filenames
        
    Returns:
        list: Filtered list with system files removed
    """
    return [f for f in file_list if not is_system_file(f)]


def should_validate_file(file_path):
    """
    Check if a file should be included in dataset validation.
    
    Args:
        file_path (str): Full or relative path to the file
        
    Returns:
        bool: True if file should be validated, False if it should be skipped
    """
    filename = os.path.basename(file_path)
    return not is_system_file(filename)


def get_ignored_files_summary(file_list):
    """
    Get a summary of which system files were ignored.
    
    Args:
        file_list (list): Original list of filenames
        
    Returns:
        dict: Summary with counts and examples of ignored files
    """
    ignored = [f for f in file_list if is_system_file(f)]
    
    summary = {
        'total_ignored': len(ignored),
        'files': ignored[:10],  # Show first 10 as examples
        'has_more': len(ignored) > 10
    }
    
    return summary