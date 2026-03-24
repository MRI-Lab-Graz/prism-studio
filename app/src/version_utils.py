from __future__ import annotations

import re
from typing import Optional, Tuple


_RELEASE_TAG_PATTERN = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", re.IGNORECASE)


def parse_release_version(tag_name: str) -> Optional[Tuple[int, int, int]]:
    """Parse a PRISM release tag into a comparable numeric tuple."""
    if not isinstance(tag_name, str):
        return None

    normalized = tag_name.strip()
    if not normalized or normalized.lower() == "unknown":
        return None

    match = _RELEASE_TAG_PATTERN.fullmatch(normalized)
    if match is None:
        return None

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


def is_newer_release_available(current_version: str, latest_version: str) -> bool:
    """Return True when the latest known release is newer than the current build."""
    current = parse_release_version(current_version)
    latest = parse_release_version(latest_version)
    if current is None or latest is None:
        return False
    return latest > current
