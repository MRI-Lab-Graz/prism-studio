"""
Cross-platform compatibility utilities for prism
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_REPLACE_RETRY_ATTEMPTS = 5
_REPLACE_RETRY_DELAY_SECONDS = 0.2


def _replace_with_retry(source, destination):
    """os.replace() with short retries for a transient Windows file lock.

    Antivirus/Windows Defender frequently holds a brief exclusive lock on a
    just-written file, which surfaces as PermissionError (WinError 32) on
    os.replace() even though nothing in PRISM itself still has the file
    open. POSIX platforms don't exhibit this, so the retry only ever loops
    when the first attempt actually raises -- no added cost on the common
    path. Mirrors the same pattern used for DatasetFixer renames.
    """
    last_error = None
    for attempt in range(_REPLACE_RETRY_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt < _REPLACE_RETRY_ATTEMPTS - 1:
                time.sleep(_REPLACE_RETRY_DELAY_SECONDS)
    raise last_error


def remove_tree(path, ignore_errors=False):
    """shutil.rmtree() that can also delete read-only git-annex trees.

    git-annex keeps annexed content as read-only objects so accidental edits
    fail loudly. POSIX only needs write permission on the *parent* directory to
    unlink a file, so a plain rmtree succeeds there; Windows refuses to unlink a
    read-only file at all. Left alone, a failed `datalad clone` leaves a partial
    dataset behind that the retry then trips over, because DataLad wants an
    empty target.

    ``ignore_errors`` keeps the best-effort semantics of the temp-dir cleanups
    without giving up the chmod retry the way ``shutil.rmtree(ignore_errors=True)``
    does - that flag suppresses ``onerror`` entirely, so read-only trees are
    never even retried.
    """

    def _make_writable_and_retry(func, target, exc_info):
        try:
            # Unlinking needs write permission on the *parent*, not the file,
            # so a read-only directory blocks deletion of everything inside it.
            parent = os.path.dirname(target)
            if parent and not os.access(parent, os.W_OK):
                os.chmod(parent, 0o700)
            # Directories need +x as well, or the recursive walk can't enter.
            os.chmod(target, 0o700 if os.path.isdir(target) else 0o600)
            func(target)
        except OSError:
            if not ignore_errors:
                raise exc_info[1]

    # ponytail: onerror= is deprecated since 3.12 in favour of onexc=, but still
    # works (verified on 3.14). CI pins 3.10 (.github/workflows/ci.yml), which
    # predates onexc, so onerror stays until that floor moves past 3.11.
    shutil.rmtree(path, onerror=_make_writable_and_retry)


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
    except (OSError, ImportError):
        return False


def normalize_line_endings(text):
    """Normalize line endings for cross-platform compatibility"""
    # Convert to Unix-style line endings, then to platform-appropriate
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", os.linesep)


def get_executable_extension():
    """Get the appropriate executable extension for the platform"""
    return ".exe" if sys.platform.startswith("win") else ""


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
        """Write text file atomically, with proper encoding.

        Writes to a temp file in the same directory first, then replaces
        the destination -- avoids a corrupted/truncated file if the
        process is interrupted mid-write, and the replace step retries
        through a transient Windows antivirus lock (see
        _replace_with_retry).
        """
        directory = Path(filepath).parent
        directory.mkdir(parents=True, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(dir=str(directory), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
                f.write(content)
            _replace_with_retry(temp_path, filepath)
        except BaseException:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise


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


def ensure_user_bin_on_path() -> None:
    """Append ~/.local/bin to PATH (where `uv tool install` puts datalad/git-annex).

    Desktop launchers and terminals opened before install don't have it yet.
    """
    user_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.isdir(user_bin) and user_bin not in parts:
        os.environ["PATH"] = os.pathsep.join(parts + [user_bin])
