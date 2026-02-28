import json
import os
from pathlib import Path

_RECENT_PROJECTS_FILENAME = "prism_recent_projects.json"
_RECENT_PROJECTS_MAX = 6


def _resolve_project_root_path(project_path_value: str) -> Path | None:
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


def _get_user_config_dir() -> Path:
    """Return a cross-platform per-user PRISM Studio config directory."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "PRISM Studio"

    if os.name == "posix" and os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "PRISM Studio"

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "prism-studio"
    return Path.home() / ".config" / "prism-studio"


def _recent_projects_file() -> Path:
    cfg_dir = _get_user_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / _RECENT_PROJECTS_FILENAME


def _normalize_recent_projects(projects: list) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()

    for item in projects:
        if not isinstance(item, dict):
            continue

        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            continue

        try:
            canonical_path = str(Path(raw_path).expanduser().resolve(strict=False))
        except Exception:
            canonical_path = raw_path

        if canonical_path in seen:
            continue

        raw_name = str(item.get("name") or "").strip()
        safe_name = raw_name or Path(canonical_path).name or canonical_path

        normalized.append({"name": safe_name, "path": canonical_path})
        seen.add(canonical_path)

        if len(normalized) >= _RECENT_PROJECTS_MAX:
            break

    return normalized


def _load_recent_projects() -> list[dict]:
    file_path = _recent_projects_file()
    if not file_path.exists():
        return []

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return _normalize_recent_projects(data)
    except Exception:
        return []


def _save_recent_projects(projects: list[dict]) -> list[dict]:
    normalized = _normalize_recent_projects(projects)
    file_path = _recent_projects_file()
    file_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized
