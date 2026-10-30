"""Where the global template library is: one answer for Studio and the commands."""

from __future__ import annotations

from pathlib import Path


def _safe_expand_path(path_str: str) -> Path:
    """Expand ``~`` and tolerate network-drive paths that raise."""
    try:
        candidate = Path(path_str)
        if "~" in path_str:
            candidate = candidate.expanduser()
        return candidate
    except (OSError, ValueError):
        return Path(path_str)


def global_survey_library_root(base_dir: Path) -> Path | None:
    """The global survey library: the configured one, else the official one, else the app's own folders."""

    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(app_root=str(base_dir))

    if lib_paths["global_library_path"]:
        candidate = _safe_expand_path(lib_paths["global_library_path"])
        if not candidate.is_absolute():
            try:
                candidate = (base_dir / candidate).resolve()
            except (OSError, ValueError):
                candidate = base_dir / candidate
        if candidate.exists() and candidate.is_dir():
            return candidate

    official_candidates = [
        base_dir / "official" / "library",
        base_dir.parent / "official" / "library",
    ]
    for candidate in official_candidates:
        try:
            candidate = candidate.resolve()
            if candidate.exists() and candidate.is_dir():
                return candidate
        except (OSError, ValueError):
            if candidate.exists() and candidate.is_dir():
                return candidate

    preferred = base_dir / "library" / "survey_i18n"
    try:
        preferred = preferred.resolve()
    except (OSError, ValueError):
        pass
    if preferred.exists() and any(preferred.glob("survey-*.json")):
        return preferred

    fallback = base_dir / "survey_library"
    try:
        fallback = fallback.resolve()
    except (OSError, ValueError):
        pass
    return fallback if fallback.exists() else None
