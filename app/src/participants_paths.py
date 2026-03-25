"""Shared path resolution helpers for participant-related files."""

from __future__ import annotations

from pathlib import Path


def participants_mapping_candidates(project_root: Path) -> list[Path]:
    """Return supported project-local locations for participants_mapping.json."""
    return [
        project_root / "participants_mapping.json",
        project_root / "code" / "participants_mapping.json",
        project_root / "code" / "library" / "participants_mapping.json",
        project_root / "code" / "library" / "survey" / "participants_mapping.json",
    ]
