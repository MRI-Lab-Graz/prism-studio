import json
from pathlib import Path

from flask import jsonify

_APP_ROOT = Path(__file__).resolve().parents[3]  # app/: where the schemas are


def handle_limesurvey_save_to_project(project_path: str | None, data: dict | None):
    if not project_path:
        return jsonify({"success": False, "error": "No project selected"}), 400

    resolved_project_path = Path(project_path)
    if not resolved_project_path.exists():
        return jsonify({"success": False, "error": "Project path does not exist"}), 400

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    templates = data.get("templates", [])
    if not templates:
        return jsonify({"success": False, "error": "No templates provided"}), 400

    from src.template_save import save_templates_to_project

    return jsonify(save_templates_to_project(templates, project_root=resolved_project_path, app_root=_APP_ROOT))


def handle_fix_participants_bids(data: dict | None):
    from src.participants_bids_fix import fix_participants_tsv

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"}), 400

    try:
        result = fix_participants_tsv(
            file_path,
            sex_mapping=data.get("sex_mapping"),
            dry_run=data.get("dry_run", False),
        )
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify(result)
