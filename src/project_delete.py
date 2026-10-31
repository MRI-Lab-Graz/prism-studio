"""Delete a project folder from disk: the one rule behind Studio's Delete button and `prism_tools project delete`."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from src.project_root import resolve_project_root_path


class ProjectDeleteRefused(ValueError):
    """The folder is not deleted; the message says why."""


def derive_project_name(root_path: Path, fallback_name: str | None = None) -> str:
    """Resolve display name from project metadata with safe fallbacks."""
    project_json = root_path / "project.json"
    if project_json.exists() and project_json.is_file():
        try:
            payload = json.loads(project_json.read_text(encoding="utf-8"))
            name = str(payload.get("name") or "").strip()
            if name:
                return name
        except Exception:
            pass

    fallback = str(fallback_name or "").strip()
    if fallback:
        return fallback

    return root_path.name


def _make_writable_and_retry(func, path, exc_info):
    """``shutil.rmtree`` onerror handler for read-only git-annex objects (annexed content is read-only)."""
    try:
        os.chmod(path, 0o700 if os.path.isdir(path) else 0o600)
        func(path)
    except OSError:
        raise exc_info[1]


def is_filesystem_root_or_home(path: Path) -> bool:
    return str(path) == path.anchor or path == Path.home()


def delete_project(path: str, confirm_name: str) -> Path:
    """Delete the project at `path` once `confirm_name` echoes its exact name. Returns the deleted folder.

    Only recognisable project folders are touched, never a filesystem root or the home directory.
    Raises ProjectDeleteRefused (nothing deleted) with the reason.
    """
    root = resolve_project_root_path(path)
    if not root or not root.exists():
        raise ProjectDeleteRefused(f"Path does not exist: {path}")
    if not ((root / "project.json").exists() or (root / "dataset_description.json").exists()):
        raise ProjectDeleteRefused(
            "This folder does not look like a PRISM project "
            "(no project.json or dataset_description.json found). "
            "Refusing to delete it."
        )
    if is_filesystem_root_or_home(root):
        raise ProjectDeleteRefused("Refusing to delete a filesystem root or home directory.")
    actual_name = derive_project_name(root, fallback_name=root.name)
    if not confirm_name or confirm_name != actual_name:
        raise ProjectDeleteRefused(
            f"Confirmation name does not match the project name. Expected '{actual_name}'."
        )
    shutil.rmtree(root, onerror=_make_writable_and_retry)
    return root
