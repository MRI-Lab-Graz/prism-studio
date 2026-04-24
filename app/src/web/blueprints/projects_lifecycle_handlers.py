import os
import json
from pathlib import Path
from typing import Any

from flask import jsonify, request, session
import requests

from .projects_helpers import _load_recent_projects, _save_recent_projects
from .projects_helpers import _resolve_project_json_path, _resolve_project_root_path
from .projects_citation_helpers import _validate_recruitment_payload

_RECRUITMENT_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_RECRUITMENT_GEOCODING_TIMEOUT_SECONDS = 5


def _normalize_dataset_type(dataset_type):
    value = str(dataset_type or "").strip().lower()
    if value in {"raw", "derivative"}:
        return value
    return "raw"


def _derive_project_name(root_path: Path, fallback_name: str | None = None) -> str:
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


def _build_project_quick_summary(root_path: Path) -> dict[str, Any]:
    """Build fast project summary metrics for UI cards.

    This intentionally avoids full validation and only scans structure basics.
    """
    try:
        from src.project_structure import get_project_quick_summary

        return get_project_quick_summary(root_path)
    except Exception:
        return {}


def handle_set_current(get_current_project, set_current_project, save_last_project):
    """Set or clear current project in session and persisted settings."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    path = data.get("path")

    if not path:
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)
        save_last_project(None, None)
        return jsonify({"success": True, "current": get_current_project()})

    name = data.get("name")

    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Path does not exist"}), 400

    resolved_root = _resolve_project_root_path(path)
    if not resolved_root:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Path must be a project directory or project.json",
                }
            ),
            400,
        )

    path = str(resolved_root)

    resolved_name = _derive_project_name(Path(path), fallback_name=name)

    set_current_project(path, resolved_name)
    save_last_project(path, resolved_name)

    summary = _build_project_quick_summary(Path(path))

    return jsonify(
        {
            "success": True,
            "current": get_current_project(),
            "project_summary": summary,
        }
    )


def handle_create_project(project_manager, set_current_project, save_last_project):
    """Create a new PRISM project and set it as current."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        recruitment_error = _validate_recruitment_payload(data.get("Recruitment"))
        if recruitment_error:
            return jsonify({"success": False, "error": recruitment_error}), 400

        config = {
            "name": data.get("name", Path(path).name),
            "authors": data.get("authors"),
            "license": data.get("license"),
            "doi": data.get("doi"),
            "keywords": data.get("keywords"),
            "acknowledgements": data.get("acknowledgements"),
            "ethics_approvals": data.get("ethics_approvals"),
            "how_to_acknowledge": data.get("how_to_acknowledge"),
            "funding": data.get("funding"),
            "references_and_links": data.get("references_and_links"),
            "hed_version": data.get("hed_version"),
            "dataset_type": _normalize_dataset_type(data.get("dataset_type")),
            "description": data.get("description"),
            "Basics": data.get("Basics"),
            "Overview": data.get("Overview"),
            "StudyDesign": data.get("StudyDesign"),
            "Recruitment": data.get("Recruitment"),
            "Eligibility": data.get("Eligibility"),
            "DataCollection": data.get("DataCollection"),
            "Procedure": data.get("Procedure"),
            "MissingData": data.get("MissingData"),
            "References": data.get("References"),
            "Conditions": data.get("Conditions"),
        }

        result = project_manager.create_project(path, config)

        if result.get("success"):
            project_name = config.get("name") or Path(path).name
            set_current_project(path, project_name)
            save_last_project(path, project_name)
            result["current_project"] = {
                "path": str(Path(path)),
                "name": project_name,
                "project_json_path": str(Path(path) / "project.json"),
            }
            return jsonify(result)

        return jsonify(result), 400
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_init_on_bids(project_manager, set_current_project, save_last_project):
    """Initialise PRISM on an existing BIDS dataset root."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        config = {
            "name": data.get("name"),
            "authors": data.get("authors"),
            "license": data.get("license"),
            "doi": data.get("doi"),
            "keywords": data.get("keywords"),
            "acknowledgements": data.get("acknowledgements"),
            "ethics_approvals": data.get("ethics_approvals"),
            "how_to_acknowledge": data.get("how_to_acknowledge"),
            "funding": data.get("funding"),
            "references_and_links": data.get("references_and_links"),
            "dataset_type": _normalize_dataset_type(data.get("dataset_type")),
            "description": data.get("description"),
        }

        result = project_manager.init_on_existing_bids(path, config)

        if result.get("success"):
            project_name = config.get("name") or Path(path).name
            set_current_project(path, project_name)
            save_last_project(path, project_name)
            result["current_project"] = {
                "path": str(Path(path)),
                "name": project_name,
                "project_json_path": str(Path(path) / "project.json"),
            }
            return jsonify(result)

        return jsonify(result), 400
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_validate_project(project_manager, set_current_project, save_last_project):
    """Validate existing project.json and set project as current when valid."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        root_path_obj = _resolve_project_root_path(path)
        project_json = _resolve_project_json_path(path)
        if not root_path_obj or not project_json:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid selection. Select either the project folder containing project.json or the project.json file itself.",
                    }
                ),
                400,
            )

        project_json_path = str(project_json)
        root_path = str(root_path_obj)

        if not os.path.exists(root_path):
            return (
                jsonify(
                    {"success": False, "error": f"Path does not exist: {root_path}"}
                ),
                400,
            )

        result = project_manager.validate_structure(root_path)
        result["success"] = True

        project_name = _derive_project_name(
            root_path_obj,
            fallback_name=session.get("current_project_name"),
        )
        set_current_project(root_path, project_name)
        save_last_project(root_path, project_name)

        result["current_project"] = {
            "path": root_path,
            "name": project_name,
            "project_json_path": project_json_path,
        }

        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_project_path_status():
    """Return lightweight availability info for a project.json path."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not isinstance(path, str) or not path.strip():
            return jsonify({"success": False, "error": "Path is required"}), 400

        path_obj = Path(path)
        exists = path_obj.exists()
        is_file = path_obj.is_file()
        is_project_json = is_file and path_obj.name == "project.json"
        resolved_project_json = _resolve_project_json_path(path)

        return jsonify(
            {
                "success": True,
                "exists": exists,
                "is_file": is_file,
                "is_project_json": is_project_json,
                "available": bool(resolved_project_json),
                "project_json_path": (
                    str(resolved_project_json) if resolved_project_json else None
                ),
            }
        )
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_recruitment_location_search():
    """Search place names for Recruitment->Location in Projects UI."""
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400

    params = {
        "name": query,
        "count": 8,
        "language": "en",
        "format": "json",
    }

    try:
        response = requests.get(
            _RECRUITMENT_GEOCODING_URL,
            params=params,
            timeout=_RECRUITMENT_GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        raw_results = payload.get("results") or []
        results: list[dict[str, Any]] = []
        for item in raw_results:
            name = (item.get("name") or "").strip()
            admin1 = (item.get("admin1") or "").strip()
            country = (item.get("country") or "").strip()
            label_parts = [part for part in [name, admin1, country] if part]
            label = ", ".join(label_parts) if label_parts else name

            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue

            results.append(
                {
                    "name": name,
                    "display_name": label,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "timezone": item.get("timezone") or "",
                }
            )

        return jsonify({"success": True, "results": results})
    except requests.RequestException as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


def handle_get_recent_projects():
    """Get recent projects from user-scoped settings storage."""
    try:
        projects = _load_recent_projects()
        return jsonify({"success": True, "projects": projects})
    except Exception as error:
        return jsonify({"success": False, "error": str(error), "projects": []}), 500


def handle_set_recent_projects():
    """Replace recent projects list in user-scoped settings storage."""
    data = request.get_json(silent=True) or {}
    projects = data.get("projects")
    if not isinstance(projects, list):
        return jsonify({"success": False, "error": "projects must be a list"}), 400

    try:
        saved = _save_recent_projects(projects)
        return jsonify({"success": True, "projects": saved})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_fix_project(project_manager):
    """Apply fix operations to a project."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        fix_codes = data.get("fix_codes")
        result = project_manager.apply_fixes(path, fix_codes)
        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_get_fixable_issues(project_manager):
    """List fixable issues for the given project path."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        issues = project_manager.get_fixable_issues(path)
        return jsonify({"success": True, "issues": issues})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500
