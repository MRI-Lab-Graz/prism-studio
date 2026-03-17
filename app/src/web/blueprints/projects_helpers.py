import json
import os
from pathlib import Path

_RECENT_PROJECTS_FILENAME = "prism_recent_projects.json"
_RECENT_PROJECTS_MAX = 5


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


def _resolve_project_json_path(project_path_value: str) -> Path | None:
    root_path = _resolve_project_root_path(project_path_value)
    if not root_path:
        return None

    project_json_path = root_path / "project.json"
    if not project_json_path.exists() or not project_json_path.is_file():
        return None

    return project_json_path


def _read_tabular_dataframe(table_path: Path, expected_delimiter: str = "\t"):
    import pandas as pd

    attempts: list[dict] = []
    if expected_delimiter:
        attempts.append({"sep": expected_delimiter})

    for candidate in (",", ";", "\t"):
        if candidate != expected_delimiter:
            attempts.append({"sep": candidate})

    attempts.append({"sep": None, "engine": "python"})

    last_error = None
    for read_kwargs in attempts:
        try:
            df = pd.read_csv(
                table_path,
                dtype=str,
                encoding="utf-8-sig",
                **read_kwargs,
            )
        except Exception as error:
            last_error = error
            continue

        if _looks_like_wrong_delimiter(df, read_kwargs.get("sep")):
            continue

        return df

    if last_error:
        raise last_error

    return pd.read_csv(
        table_path, dtype=str, encoding="utf-8-sig", sep=expected_delimiter
    )


def _looks_like_wrong_delimiter(df, used_delimiter: str | None) -> bool:
    if len(df.columns) != 1:
        return False

    header = str(df.columns[0])
    suspicious_delimiters = {",", ";", "\t"}
    if used_delimiter in suspicious_delimiters:
        suspicious_delimiters.remove(used_delimiter)

    return any(delimiter in header for delimiter in suspicious_delimiters)


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
