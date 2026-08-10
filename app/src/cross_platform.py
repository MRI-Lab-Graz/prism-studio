"""
Cross-platform compatibility utilities for prism
"""

import os
import sys
from pathlib import Path


def normalize_path(path):
    """Normalize path separators for cross-platform compatibility"""
    return str(Path(path).as_posix()) if path else path


def safe_path_join(*args):
    """Safe path joining that works across platforms"""
    return str(Path(*args))


def get_platform_info():
    """Get platform-specific information"""
    return {
        "platform": sys.platform,
        "is_windows": sys.platform.startswith("win"),
        "is_posix": os.name == "posix",
        "path_separator": os.sep,
        "line_separator": os.linesep,
    }


def windows_symlinks_supported():
    """Return True/False on Windows, None on every other platform.

    git-annex tracks files as symlinks into `.git/annex/objects/` by
    default. Creating a symlink on Windows requires Developer Mode
    (Win10 1703+) or admin rights -- there is no API to query that
    privilege directly, so this actually creates and removes a throwaway
    symlink in a temp directory, the same way Windows itself decides.
    When unsupported, git-annex automatically falls back to an "adjusted
    unlocked branch" (files materialize as real files instead of
    symlinks) -- a supported mode, not an error, but worth surfacing so
    it isn't silent.
    """
    if not sys.platform.startswith("win"):
        return None

    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = os.path.join(tmp_dir, "target")
            link = os.path.join(tmp_dir, "link")
            with open(target, "w", encoding="utf-8"):
                pass
            os.symlink(target, link)
        return True
    except OSError:
        return False


def windows_long_paths_enabled():
    """Return True/False on Windows, None on every other platform.

    Windows enforces a 260-character MAX_PATH by default. git-annex's
    hashed object-store paths
    (`.git/annex/objects/<2>/<2>/SHA256E-.../<original filename>`) can
    exceed that on deeply nested datasets even when the original path
    was well within limits. The only way to check is the registry value
    Windows itself consults; any failure to read it (missing key, no
    `winreg`, permission denied) is treated as "not confirmed enabled"
    rather than assumed safe, since a false warning is harmless but a
    missed one causes a mid-operation failure.
    """
    if not sys.platform.startswith("win"):
        return None

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
        return bool(value)
    except OSError:
        return False


def normalize_line_endings(text):
    """Normalize line endings for cross-platform compatibility"""
    # Convert to Unix-style line endings, then to platform-appropriate
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", os.linesep)


def get_executable_extension():
    """Get the appropriate executable extension for the platform"""
    return ".exe" if sys.platform.startswith("win") else ""


def case_insensitive_glob(pattern, path="."):
    """Case-insensitive file globbing for Windows compatibility"""
    from pathlib import Path
    import fnmatch

    path_obj = Path(path)
    if not path_obj.exists():
        return []

    # On Windows, filesystem is case-insensitive anyway
    # On Unix, we need to do case-insensitive matching manually
    if sys.platform.startswith("win"):
        return list(path_obj.glob(pattern))
    else:
        # Manual case-insensitive matching for Unix systems
        results = []
        for item in path_obj.rglob("*"):
            if fnmatch.fnmatch(item.name.lower(), pattern.lower()):
                results.append(item)
        return results


class CrossPlatformFile:
    """File operations that work consistently across platforms"""

    @staticmethod
    def read_text(filepath, encoding="utf-8"):
        """Read text file with proper encoding handling"""
        try:
            # Try UTF-8 first (most common)
            with open(filepath, "r", encoding=encoding, newline="") as f:
                content = f.read()
            return normalize_line_endings(content)
        except UnicodeDecodeError:
            # Fallback to system default encoding
            with open(
                filepath, "r", encoding=sys.getdefaultencoding(), newline=""
            ) as f:
                content = f.read()
            return normalize_line_endings(content)

    @staticmethod
    def write_text(filepath, content, encoding="utf-8"):
        """Write text file with proper encoding"""
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding=encoding, newline="") as f:
            f.write(content)


def get_temp_dir():
    """Get platform-appropriate temporary directory"""
    import tempfile

    return tempfile.gettempdir()


def is_case_sensitive_filesystem(path="."):
    """Check if the filesystem is case-sensitive"""
    import tempfile
    import os

    # Create a temporary file with lowercase name
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, dir=path, suffix=".tmp"
    ) as f:
        temp_path = f.name
        f.write("test")

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
    """Validate filename for cross-platform compatibility.

    Checks are always applied regardless of host OS because PRISM datasets
    are intended to be portable across Windows, macOS, and Linux.
    """
    issues = []

    # Windows filename restrictions — always checked for portability
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in reserved_names:
        issues.append(f"Filename '{filename}' uses Windows reserved name")

    # Invalid characters in Windows
    invalid_chars = '<>:"|?*'
    for char in invalid_chars:
        if char in filename:
            issues.append(
                f"Filename '{filename}' contains invalid character '{char}' for Windows"
            )

    # Trailing spaces or dots (invalid on Windows)
    if filename.endswith(" ") or filename.endswith("."):
        issues.append(
            f"Filename '{filename}' ends with space or dot (invalid on Windows)"
        )

    # General cross-platform issues
    if len(filename) > 255:
        issues.append(f"Filename '{filename}' too long (>255 characters)")

    return issues


def find_case_insensitive_id_collisions(ids):
    """Group distinct-but-case-variant ids (e.g. ``sub-Ab`` vs ``sub-ab``).

    Returns ``{lowered_id: [original_variants]}``, including only groups
    with more than one distinct original spelling.

    PRISM treats participant/session labels as case-sensitive everywhere
    in its own data model (participants.tsv, the participants-merge logic),
    but on a case-insensitive filesystem (the default on macOS and
    Windows) two such ids resolve to the identical on-disk path. Writing
    per-subject output files for both silently overwrites one with the
    other's content with no error or warning. This check is always
    applied regardless of host OS — same philosophy as
    ``validate_filename_cross_platform`` — because a dataset can be
    created on one platform and opened on another.
    """
    groups: dict[str, list[str]] = {}
    seen_per_group: dict[str, set[str]] = {}
    for original in ids:
        if not original:
            continue
        key = str(original).lower()
        seen = seen_per_group.setdefault(key, set())
        if original not in seen:
            seen.add(original)
            groups.setdefault(key, []).append(original)
    return {key: variants for key, variants in groups.items() if len(variants) > 1}


def describe_case_insensitive_id_collisions(ids, *, label="participant"):
    """Return a human-readable error message for colliding ids, or None.

    Convenience wrapper around find_case_insensitive_id_collisions for
    converters that just need a ready-to-raise message.
    """
    collisions = find_case_insensitive_id_collisions(ids)
    if not collisions:
        return None
    details = "; ".join(
        f"{'/'.join(sorted(variants))}" for variants in collisions.values()
    )
    return (
        f"These {label} ids differ only by case and would silently overwrite "
        f"each other's files on case-insensitive filesystems (default on "
        f"macOS/Windows): {details}. Rename one of each pair before "
        f"converting."
    )
