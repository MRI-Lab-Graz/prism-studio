from pathlib import Path

from flask import current_app, jsonify, request

from .projects_helpers import _resolve_requested_or_current_project_root


def handle_generate_methods_section(
    get_current_project,
    read_project_json,
    get_bids_file_path,
    compute_participant_stats,
):
    """Generate a publication-ready methods section from project.json metadata."""
    from src.methods_project import build_methods
    from src.reporting import _md_to_html

    data = request.get_json() or {}
    lang = str(data.get("language", "en") or "en").strip().lower()
    if lang not in {"en", "de"}:
        lang = "en"
    detail_level = data.get("detail_level", "standard")

    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            data.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    project_data = read_project_json(project_path)
    if not project_data:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "No project metadata available. Fill in your project.json to generate a methods section.",
                }
            ),
            404,
        )

    try:
        result = build_methods(
            project_path,
            lang=lang,
            detail_level=detail_level,
            app_root=str(Path(current_app.root_path)),
            project_data=project_data,
            compute_participant_stats=compute_participant_stats,
        )
        return jsonify(
            {
                "success": True,
                "md": result.md,
                "html": _md_to_html(result.md),
                "filename_base": f"methods_section_{lang}",
                "sections_used": result.sections_used,
                "warnings": result.warnings,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
