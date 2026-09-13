import json
from pathlib import Path

from flask import jsonify


def handle_limesurvey_save_to_project(project_path: str | None, data: dict | None):
    from src.cross_platform import CrossPlatformFile
    from werkzeug.utils import secure_filename

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

    library_survey_path = resolved_project_path / "code" / "library" / "survey"
    library_survey_path.mkdir(parents=True, exist_ok=True)

    saved_files = []
    errors = []

    for template in templates:
        filename = template.get("filename")
        content = template.get("content")

        if not filename or content is None:
            errors.append("Invalid template entry: missing filename or content")
            continue

        safe_filename = secure_filename(filename)
        if not safe_filename:
            errors.append(f"Invalid filename: {filename}")
            continue

        if not safe_filename.endswith(".json"):
            safe_filename += ".json"

        file_path = library_survey_path / safe_filename

        try:
            json_content = json.dumps(content, indent=2, ensure_ascii=False)
            CrossPlatformFile.write_text(str(file_path), json_content)
            saved_files.append({"filename": safe_filename, "path": str(file_path)})
        except Exception as e:
            errors.append(f"Failed to save {safe_filename}: {str(e)}")

    return jsonify(
        {
            "success": len(saved_files) > 0,
            "saved_files": saved_files,
            "saved_count": len(saved_files),
            "library_path": str(library_survey_path),
            "errors": errors if errors else None,
        }
    )


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
