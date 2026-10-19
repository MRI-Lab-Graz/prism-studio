"""Is a PRISM project complete enough to work with? (one rule for CLI and GUI)

A folder without project.json is not a PRISM project and is never gated.
Spec: docs/superpowers/specs/2026-10-15-project-required-fields-gate-design.md
"""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FIELDS = (
    ("Basics", "Name"),
    ("Basics", "Authors"),
    ("Basics", "Keywords"),
    ("StudyDesign", "Timepoints"),
)
_TIMEPOINT_VALUES = ("single", "multiple")


class ProjectNotReadyError(ValueError):
    def __init__(self, missing: list[str], message: str | None = None) -> None:
        self.missing = missing
        super().__init__(message or not_ready_message(missing))


def not_ready_message(missing: list[str]) -> str:
    return (
        "Tools are blocked until these required fields are set on the Projects "
        "page: " + ", ".join(missing) + "."
    )


def _root(project_path) -> Path:
    path = Path(project_path).expanduser()
    return path.parent if path.is_file() else path


def _filled(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_filled(v) for v in value)
    return value is not None


def missing_required_fields(project_path) -> list[str]:
    pj = _root(project_path) / "project.json"
    if not pj.is_file():
        return []
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectNotReadyError([], f"{pj} could not be read: {exc}") from exc
    data = data if isinstance(data, dict) else {}
    missing = []
    for section, field in REQUIRED_FIELDS:
        value = (data.get(section) or {}).get(field) if isinstance(data.get(section), dict) else None
        ok = value in _TIMEPOINT_VALUES if field == "Timepoints" else _filled(value)
        if not ok:
            missing.append(field)
    return missing


def require_project_ready(project_path) -> None:
    missing = missing_required_fields(project_path)
    if missing:
        raise ProjectNotReadyError(missing)
