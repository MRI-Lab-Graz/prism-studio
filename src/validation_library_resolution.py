"""Shared default-library-path resolution for dataset validation.

Both entry points that validate a PRISM dataset need to pick a template
library when the caller doesn't specify one explicitly:

- The Studio GUI's Validate Dataset page
  (app/src/web/blueprints/validation.py).
- The CLI's bare `prism <dataset>` validate (app/prism.py).

Before this module existed, only the GUI applied a 3-tier fallback
(project `library/` -> project `code/library/` -> configured/default
global library); the CLI's `--library` had no default at all, so omitting
it meant `library_path=None` all the way down to the validator's own,
much narrower sidecar search. Validating the same dataset with "no library
specified" could therefore resolve different sidecars depending on GUI vs.
CLI — see docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-6.
"""

from __future__ import annotations

from pathlib import Path

from src.config import get_effective_library_paths


def _safe_expand_path(path_value: str) -> Path:
    """Expand and resolve a path without breaking network-style locations."""
    candidate = Path(path_value).expanduser()
    try:
        return candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        return candidate


def default_global_validation_library_path(app_root: str) -> str:
    """Configured global library, falling back to `<app_root>/survey_library`."""
    lib_paths = get_effective_library_paths(app_root=app_root)
    configured_path = lib_paths.get("global_library_path")
    if configured_path:
        candidate = _safe_expand_path(configured_path)
        if candidate.exists() and candidate.is_dir():
            return str(candidate)

    return str(_safe_expand_path(str(Path(app_root) / "survey_library")))


def default_validation_library_path(
    app_root: str, project_path: str | None = None
) -> str:
    """Resolve the library path to use when the caller doesn't override it.

    Checks `<project>/library` then `<project>/code/library` first (a
    project may ship its own template library), then falls back to the
    configured/default global library.
    """
    if project_path:
        project_root = _safe_expand_path(project_path)
        if project_root.is_file():
            project_root = project_root.parent

        for candidate in (project_root / "library", project_root / "code" / "library"):
            if candidate.exists() and candidate.is_dir():
                return str(candidate)

    return default_global_validation_library_path(app_root)
