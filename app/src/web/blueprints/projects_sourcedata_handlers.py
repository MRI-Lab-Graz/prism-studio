from pathlib import Path

from flask import jsonify, request, send_file

from .projects_helpers import _resolve_project_root_path


def handle_get_sourcedata_files(get_current_project):
    """List survey-compatible files in the project's sourcedata/ folder."""
    explicit_project_path = str(request.args.get("project_path") or "").strip()
    if explicit_project_path:
        project_path = _resolve_project_root_path(explicit_project_path)
        if project_path is None:
            return jsonify({"error": "Invalid project path"}), 400
    else:
        current = get_current_project()
        current_project_path = str((current or {}).get("path") or "").strip()
        if not current_project_path:
            return jsonify({"files": [], "sourcedata_exists": False})

        project_path = _resolve_project_root_path(current_project_path)
        if project_path is None:
            return jsonify({"files": [], "sourcedata_exists": False})

    sourcedata_dir = project_path / "sourcedata"

    if not sourcedata_dir.exists() or not sourcedata_dir.is_dir():
        return jsonify({"files": [], "sourcedata_exists": False})

    supported_extensions = {".xlsx", ".csv", ".tsv", ".lsa", ".lss"}
    files = []
    for candidate in sorted(sourcedata_dir.rglob("*")):
        if candidate.is_file() and candidate.suffix.lower() in supported_extensions:
            # Use a posix-style relative path so subdirectory files are found
            # (e.g. "wide_to_long/data.csv"). The serve endpoint reconstructs
            # the full path via project/sourcedata/<name>, which pathlib handles
            # correctly on all platforms.
            relative_name = candidate.relative_to(sourcedata_dir).as_posix()
            files.append(
                {
                    "name": relative_name,
                    "path": str(candidate),
                    "size": candidate.stat().st_size,
                    "extension": candidate.suffix.lower(),
                }
            )

    return jsonify({"files": files, "sourcedata_exists": True})


def handle_get_sourcedata_file(get_current_project):
    """Serve a file from the project's sourcedata/ folder."""
    explicit_project_path = str(request.args.get("project_path") or "").strip()
    if explicit_project_path:
        project_path = _resolve_project_root_path(explicit_project_path)
        if project_path is None:
            return jsonify({"error": "Invalid project path"}), 400
    else:
        current = get_current_project()
        current_project_path = str((current or {}).get("path") or "").strip()
        if not current_project_path:
            return jsonify({"error": "No project selected"}), 400

        project_path = _resolve_project_root_path(current_project_path)
        if project_path is None:
            return jsonify({"error": "Project path does not exist"}), 404

    filename = request.args.get("name")
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    file_path = (project_path / "sourcedata" / filename).resolve()

    sourcedata_dir = (project_path / "sourcedata").resolve()
    if not str(file_path).startswith(str(sourcedata_dir)):
        return jsonify({"error": "Invalid filename"}), 400

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": f"File not found: {filename}"}), 404

    return send_file(str(file_path), as_attachment=True, download_name=file_path.name)
