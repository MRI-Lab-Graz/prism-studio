from pathlib import Path

from flask import Response, current_app, jsonify, request

from .projects_helpers import _resolve_requested_or_current_project_root


def _build_for_request(get_current_project, read_project_json, compute_participant_stats):
    """Shared by generate and export: resolve the project and build the methods result.

    Returns ``(result, lang, None)`` or ``(None, lang, error_response)``.
    """
    from src.methods_project import build_methods

    data = request.get_json() or {}
    lang = str(data.get("language", "en") or "en").strip().lower()
    if lang not in {"en", "de"}:
        lang = "en"

    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            data.get("project_path"),
        )
    )
    if project_path is None:
        return None, lang, (jsonify({"success": False, "error": error_message}), status_code)

    project_data = read_project_json(project_path)
    if not project_data:
        return None, lang, (
            jsonify(
                {
                    "success": False,
                    "error": "No project metadata available. Fill in your project.json to generate a methods section.",
                }
            ),
            404,
        )

    result = build_methods(
        project_path,
        lang=lang,
        detail_level=data.get("detail_level", "standard"),
        app_root=str(Path(current_app.root_path)),
        project_data=project_data,
        compute_participant_stats=compute_participant_stats,
    )
    return result, lang, None


def handle_generate_methods_section(
    get_current_project,
    read_project_json,
    get_bids_file_path,
    compute_participant_stats,
):
    """Generate a publication-ready methods section from project.json metadata."""
    from src.reporting import _md_to_html

    try:
        result, lang, error = _build_for_request(
            get_current_project, read_project_json, compute_participant_stats
        )
        if error:
            return error
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


_EXPORT_FORMATS = ("docx", "tex", "bib")


def handle_export_methods(get_current_project, read_project_json, compute_participant_stats):
    """Download the methods section as Word, TeX or BibTeX (same render as the CLI)."""
    from src.methods_project import render_methods
    from src.text_export import MIME

    fmt = str((request.get_json() or {}).get("format", "")).strip().lower()
    if fmt not in _EXPORT_FORMATS:
        return jsonify({"success": False, "error": f"Unknown format {fmt!r}"}), 400
    try:
        result, lang, error = _build_for_request(
            get_current_project, read_project_json, compute_participant_stats
        )
        if error:
            return error
        data = render_methods(result, fmt)
    except RuntimeError as e:  # python-docx missing
        return jsonify({"success": False, "error": str(e)}), 501
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    filename = "references.bib" if fmt == "bib" else f"methods_section_{lang}.{fmt}"  # \bibliography{references}
    return Response(
        data,
        mimetype=MIME.get(fmt, "text/plain"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
