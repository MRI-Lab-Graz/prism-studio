import json
from pathlib import Path

from flask import current_app, jsonify, request

from src.config import load_config, save_config
from src.cross_platform import safe_path_join
from src.schema_manager import get_available_schema_versions


def _get_schema_dir() -> str:
    return safe_path_join(current_app.root_path, "schemas")


def _get_schema_versions() -> list[str]:
    versions = get_available_schema_versions(_get_schema_dir())
    return versions or ["stable"]


def _schema_version_is_explicit(config_path: str | None) -> bool:
    """Return True only when schemaVersion is explicitly written in the config file."""
    if not config_path:
        return False
    p = Path(config_path)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return "schemaVersion" in data
    except Exception:
        return False


def handle_get_project_schema_config(get_current_project):
    current = get_current_project()
    versions = _get_schema_versions()
    selected_version = "stable"
    config_path = None

    project_path = current.get("path")
    if project_path:
        config = load_config(project_path)
        selected_version = (config.schema_version or "stable").strip() or "stable"
        config_path = config._config_path

        # Backward compatibility: persist "stable" when no explicit schemaVersion exists
        if not _schema_version_is_explicit(config_path):
            config.schema_version = "stable"
            filename = Path(config_path).name if config_path else ".prismrc.json"
            config_path = save_config(config, project_path, filename=filename)

    return jsonify(
        {
            "success": True,
            "schema_version": selected_version,
            "available_versions": versions,
            "config_path": config_path,
        }
    )


def handle_save_project_schema_config(get_current_project):
    current = get_current_project()
    project_path = current.get("path")
    if not project_path:
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_root = Path(project_path)
    if not project_root.exists() or not project_root.is_dir():
        return jsonify({"success": False, "error": "Project path does not exist"}), 404

    payload = request.get_json(silent=True) or {}
    requested_version = (
        str(payload.get("schema_version") or "stable").strip() or "stable"
    )
    available_versions = _get_schema_versions()
    if requested_version not in available_versions:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Unknown schema version: {requested_version}",
                    "available_versions": available_versions,
                }
            ),
            400,
        )

    config = load_config(str(project_root))
    config.schema_version = requested_version
    filename = (
        Path(config._config_path).name if config._config_path else ".prismrc.json"
    )
    saved_path = save_config(config, str(project_root), filename=filename)

    return jsonify(
        {
            "success": True,
            "schema_version": requested_version,
            "available_versions": available_versions,
            "config_path": saved_path,
        }
    )
