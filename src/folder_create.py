"""Create a folder for the file picker's "New folder" button."""
import re
from pathlib import Path

# Rejected on every OS, not just Windows: datasets travel between machines.
_BAD_CHARS = re.compile(r'[<>:"/\|?*\x00-\x1f]')
_WINDOWS_RESERVED = re.compile(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", re.IGNORECASE)


def create_folder(parent, name: str) -> Path:
    """Make `name` inside `parent`; raise ValueError with a user-facing reason."""
    name = name.strip()
    if not name or name in {".", ".."}:
        raise ValueError("Enter a folder name.")
    if _BAD_CHARS.search(name):
        raise ValueError('A folder name cannot contain \ / : * ? " < > | or control characters.')
    if name.endswith((".", " ")) or _WINDOWS_RESERVED.fullmatch(name):
        raise ValueError(f"'{name}' is not a valid folder name on Windows.")
    if not str(parent).strip() or not Path(parent).is_dir():
        raise ValueError(f"'{parent}' is not a folder.")
    target = Path(parent) / name
    if target.exists():
        raise ValueError(f"'{name}' already exists here.")
    target.mkdir()
    return target
