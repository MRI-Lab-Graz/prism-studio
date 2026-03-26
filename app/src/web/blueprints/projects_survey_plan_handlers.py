"""
Survey version plan API handlers for the projects blueprint.

Routes:
    GET  /api/projects/survey-plan          - read mapping + available variants
    POST /api/projects/survey-plan          - save mapping
    POST /api/projects/survey-plan/refresh  - re-discover and enrich
"""

from pathlib import Path

from flask import current_app, jsonify, request

from src.survey_version_plan import (
    discover_survey_variants,
    enrich_and_save_survey_plan,
    load_survey_plan,
    save_survey_plan,
)


def _library_path() -> Path:
    return Path(current_app.root_path).parent / "official"


def handle_get_survey_plan(get_current_project):
    current = get_current_project()
    project_path_str = current.get("path")
    if not project_path_str:
        return jsonify({"success": False, "error": "No project loaded"}), 400

    project_path = Path(project_path_str)
    plan = load_survey_plan(project_path)
    available = discover_survey_variants(_library_path())

    return jsonify(
        {
            "success": True,
            "survey_version_mapping": plan["survey_version_mapping"],
            "survey_plan_settings": plan["survey_plan_settings"],
            "available": available,
        }
    )


def handle_save_survey_plan(get_current_project):
    current = get_current_project()
    project_path_str = current.get("path")
    if not project_path_str:
        return jsonify({"success": False, "error": "No project loaded"}), 400

    body = request.get_json(silent=True) or {}
    mapping = body.get("survey_version_mapping")
    settings = body.get("survey_plan_settings")

    if not isinstance(mapping, dict):
        return (
            jsonify(
                {"success": False, "error": "survey_version_mapping must be an object"}
            ),
            400,
        )

    project_path = Path(project_path_str)
    save_survey_plan(project_path, mapping, settings)
    return jsonify({"success": True})


def handle_refresh_survey_plan(get_current_project):
    """Re-scan the library and add any newly discovered surveys to the mapping."""
    current = get_current_project()
    project_path_str = current.get("path")
    if not project_path_str:
        return jsonify({"success": False, "error": "No project loaded"}), 400

    project_path = Path(project_path_str)
    result = enrich_and_save_survey_plan(project_path, _library_path())
    return jsonify(
        {
            "success": True,
            "survey_version_mapping": result["survey_version_mapping"],
            "added": result["added"],
            "available": result["available"],
        }
    )
