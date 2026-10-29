"""The user's personal template library: an optional folder of their own, used by every project."""

from __future__ import annotations

from pathlib import Path

from src.config import get_effective_library_paths

NOT_SET = "No personal library is set. Choose a folder under Settings > Personal Template Library first."


def personal_library_path(app_root, app_settings=None) -> Path | None:
    configured = get_effective_library_paths(app_root=str(app_root), app_settings=app_settings)["personal_library_path"]
    return Path(configured) if configured else None


def personal_library_folder(modality: str, app_root, app_settings=None) -> Path:
    """Where this modality's personal templates live; raises RuntimeError when no personal library is set."""
    library = personal_library_path(app_root, app_settings)
    if library is None:
        raise RuntimeError(NOT_SET)
    return library / modality
