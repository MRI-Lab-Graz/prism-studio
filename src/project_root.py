"""Resolve a user-supplied project path (folder or project.json) to its root."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root_path(project_path_value: str) -> Path | None:
    if not project_path_value:
        return None

    path_obj = Path(project_path_value)
    if not path_obj.exists():
        return None

    if path_obj.is_file() and path_obj.name == "project.json":
        return path_obj.parent

    if path_obj.is_dir():
        return path_obj

    return None


def resolve_existing_project_root(project_path_value: str | Path | None) -> Path | None:
    """Resolve a session project path to an existing project root directory."""
    raw_value = str(project_path_value or "").strip()
    if not raw_value:
        return None
    return resolve_project_root_path(raw_value)


def require_existing_project_root(
    project_path_value: str | Path | None,
    *,
    missing_message: str,
    missing_path_message: str,
) -> Path:
    """Resolve and require an existing project root for project-bound converters."""
    raw_value = str(project_path_value or "").strip()
    if not raw_value:
        raise ValueError(missing_message)

    project_root = resolve_existing_project_root(raw_value)
    if project_root is None:
        raise FileNotFoundError(missing_path_message)

    return project_root
