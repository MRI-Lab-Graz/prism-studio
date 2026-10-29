"""Which survey template library a conversion uses: one answer for the CLI and the GUI.

Order: the project's ``code/library``, then the project's ``official/library``, then the
configured global library, then the default folders next to the app.
"""

from __future__ import annotations

from pathlib import Path

from src.config import get_effective_library_paths


def _has_templates(path: Path) -> bool:
    return path.is_dir() and any(survey_templates_dir(path).glob("survey-*.json"))


def survey_templates_dir(library_root: Path) -> Path:
    """The folder holding the ``survey-*.json`` files: ``survey/`` inside a library root, if there is one."""
    return library_root / "survey" if (library_root / "survey").is_dir() else library_root


def resolve_survey_library(project_path, app_root) -> Path:
    if project_path:
        root = Path(project_path).expanduser()
        root = root.parent if root.is_file() else root
        code_library = root / "code" / "library"
        if code_library.is_dir():  # used even when empty: project templates are always tried first
            return code_library
        official = root / "official" / "library"
        for candidate in (official, official / "survey"):
            if _has_templates(candidate):
                return candidate

    app_root = Path(app_root)
    configured = get_effective_library_paths(app_root=str(app_root)).get("global_library_path")
    if configured and Path(configured).expanduser().is_dir():
        return Path(configured).expanduser()
    for default in (app_root / "library" / "survey_i18n", app_root / "survey_library", app_root / "official" / "library"):
        if default.is_dir():
            return default
    raise FileNotFoundError(
        "No survey library found. Please provide templates in project /code/library (preferred), "
        "project /official/library, or configure a global library."
    )
