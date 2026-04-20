import json
from pathlib import Path

from flask import current_app, jsonify, request

from src.config import load_config, save_config
from src.cross_platform import safe_path_join
from src.schema_manager import get_available_schema_versions
from .projects_helpers import (
    _resolve_project_root_path,
    _resolve_requested_or_current_project_root,
)


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
    versions = _get_schema_versions()
    selected_version = "stable"
    config_path = None

    project_root, error_message, status_code = _resolve_requested_or_current_project_root(
        get_current_project,
        request.args.get("project_path"),
    )
    if project_root is not None:
        config = load_config(str(project_root))
        selected_version = (config.schema_version or "stable").strip() or "stable"
        config_path = config._config_path

        # Backward compatibility: persist "stable" when no explicit schemaVersion exists
        if not _schema_version_is_explicit(config_path):
            config.schema_version = "stable"
            filename = Path(config_path).name if config_path else ".prismrc.json"
            config_path = save_config(config, str(project_root), filename=filename)
    elif status_code not in (None, 400):
        return jsonify({"success": False, "error": error_message}), status_code

    return jsonify(
        {
            "success": True,
            "schema_version": selected_version,
            "available_versions": versions,
            "config_path": config_path,
        }
    )


def handle_save_project_schema_config(get_current_project):
    payload = request.get_json(silent=True) or {}
    project_root, error_message, status_code = _resolve_requested_or_current_project_root(
        get_current_project,
        payload.get("project_path"),
    )
    if project_root is None:
        return jsonify({"success": False, "error": error_message}), status_code

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


def handle_get_project_preferences(get_current_project, namespace: str | None = None):
    """Get project UI preferences from .prismrc.json.

    Args:
        get_current_project: Function to get current project context
        namespace: Optional namespace (e.g. 'recipes') to fetch only that section

    Returns:
        JSON response with preferences
    """
    current = get_current_project()
    explicit_project_path = str(request.args.get("project_path") or "").strip()

    if explicit_project_path:
        project_root = _resolve_project_root_path(explicit_project_path)
        if project_root is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
    else:
        project_path = current.get("path")
        if not project_path:
            return jsonify({"success": False, "error": "No project selected"}), 400
        project_root = _resolve_project_root_path(str(project_path))
        if project_root is None:
            return jsonify({"success": False, "error": "Project path does not exist"}), 404

    config = load_config(str(project_root))
    prefs = config.project_preferences or {}

    if namespace:
        return jsonify({"success": True, "preferences": prefs.get(namespace, {})})

    return jsonify({"success": True, "preferences": prefs})


def handle_save_project_preferences(get_current_project, namespace: str | None = None):
    """Save project UI preferences to .prismrc.json.

    Args:
        get_current_project: Function to get current project context
        namespace: Optional namespace (e.g. 'recipes') to update only that section

    Returns:
        JSON response with saved preferences
    """
    payload = request.get_json(silent=True) or {}
    new_prefs = payload.get("preferences", {})
    explicit_project_path = str(payload.get("project_path") or "").strip()

    if explicit_project_path:
        project_root = _resolve_project_root_path(explicit_project_path)
        if project_root is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400
    else:
        current = get_current_project()
        project_path = current.get("path")
        if not project_path:
            return jsonify({"success": False, "error": "No project selected"}), 400
        project_root = _resolve_project_root_path(str(project_path))
        if project_root is None:
            return jsonify({"success": False, "error": "Project path does not exist"}), 404

    if not isinstance(new_prefs, dict):
        return (
            jsonify({"success": False, "error": "Preferences must be an object"}),
            400,
        )

    config = load_config(str(project_root))
    current_prefs = config.project_preferences or {}

    if namespace:
        # Merge into specific namespace
        current_prefs[namespace] = {
            **(current_prefs.get(namespace) or {}),
            **new_prefs,
        }
    else:
        # Replace all preferences
        current_prefs = new_prefs

    config.project_preferences = current_prefs
    filename = (
        Path(config._config_path).name if config._config_path else ".prismrc.json"
    )
    saved_path = save_config(config, str(project_root), filename=filename)

    return jsonify(
        {
            "success": True,
            "preferences": (
                current_prefs if not namespace else current_prefs.get(namespace, {})
            ),
            "config_path": saved_path,
        }
    )
