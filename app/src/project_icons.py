"""Project icon utilities.

Defines a curated set of non-provocative, science-oriented icon classes and
helpers to normalize, assign, and persist icons in project.json metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from random import SystemRandom
from typing import Any

from src.cross_platform import CrossPlatformFile

# Curated Font Awesome icon classes for project/study identity.
_PROJECT_ICON_CLASSES: tuple[str, ...] = (
    "fas fa-brain",
    "fas fa-microscope",
    "fas fa-dna",
    "fas fa-atom",
    "fas fa-flask",
    "fas fa-vial",
    "fas fa-wave-square",
    "fas fa-stethoscope",
    "fas fa-chart-line",
    "fas fa-notes-medical",
)

_random = SystemRandom()


def get_project_icon_classes() -> tuple[str, ...]:
    """Return the curated set of allowed project icon classes."""
    return _PROJECT_ICON_CLASSES


def normalize_project_icon(icon_value: Any) -> str | None:
    """Return a valid icon class or None when the value is unknown/invalid."""
    icon = str(icon_value or "").strip()
    if not icon:
        return None
    return icon if icon in _PROJECT_ICON_CLASSES else None


def choose_random_project_icon() -> str:
    """Choose a random icon class from the curated icon set."""
    return _random.choice(_PROJECT_ICON_CLASSES)


def _project_json_path(project_root: Path | str) -> Path:
    return Path(project_root) / "project.json"


def _load_project_json_payload(project_root: Path | str) -> dict[str, Any] | None:
    project_json_path = _project_json_path(project_root)
    if not project_json_path.exists() or not project_json_path.is_file():
        return None

    try:
        payload = json.loads(CrossPlatformFile.read_text(str(project_json_path)))
    except Exception:
        return None

    return payload if isinstance(payload, dict) else None


def _persist_project_json_payload(
    project_root: Path | str,
    payload: dict[str, Any],
) -> None:
    project_json_path = _project_json_path(project_root)
    CrossPlatformFile.write_text(
        str(project_json_path),
        json.dumps(payload, indent=2, ensure_ascii=False),
    )


def read_project_icon(project_root: Path | str) -> str | None:
    """Read and normalize the icon from project.json when present."""
    payload = _load_project_json_payload(project_root)
    if not payload:
        return None
    return normalize_project_icon(payload.get("icon"))


def resolve_project_icon(
    project_root: Path | str,
    fallback_icon: Any = None,
    persist_when_missing: bool = True,
) -> str:
    """Resolve a project's icon, assigning a random one when missing.

    If ``project.json`` exists and no valid icon is present, this writes back the
    resolved icon to make the assignment stable across sessions.
    """
    payload = _load_project_json_payload(project_root)

    if payload:
        existing_icon = normalize_project_icon(payload.get("icon"))
        if existing_icon:
            return existing_icon

    resolved_icon = normalize_project_icon(fallback_icon) or choose_random_project_icon()

    if persist_when_missing and payload is not None:
        payload["icon"] = resolved_icon
        _persist_project_json_payload(project_root, payload)

    return resolved_icon
