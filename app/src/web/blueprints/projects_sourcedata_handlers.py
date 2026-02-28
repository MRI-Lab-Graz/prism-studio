from pathlib import Path

from flask import jsonify, request, send_file


def handle_get_sourcedata_files(get_current_project):
    """List survey-compatible files in the project's sourcedata/ folder."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"files": [], "sourcedata_exists": False})

    project_path = Path(current["path"])
    sourcedata_dir = project_path / "sourcedata"

    if not sourcedata_dir.exists() or not sourcedata_dir.is_dir():
        return jsonify({"files": [], "sourcedata_exists": False})

    supported_extensions = {".xlsx", ".csv", ".tsv", ".lsa", ".lss"}
    files = []
    for candidate in sorted(sourcedata_dir.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in supported_extensions:
            files.append(
                {
                    "name": candidate.name,
                    "path": str(candidate),
                    "size": candidate.stat().st_size,
                    "extension": candidate.suffix.lower(),
                }
            )

    return jsonify({"files": files, "sourcedata_exists": True})


def handle_get_sourcedata_file(get_current_project):
    """Serve a file from the project's sourcedata/ folder."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"error": "No project selected"}), 400

    filename = request.args.get("name")
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    project_path = Path(current["path"])
    file_path = (project_path / "sourcedata" / filename).resolve()

    sourcedata_dir = (project_path / "sourcedata").resolve()
    if not str(file_path).startswith(str(sourcedata_dir)):
        return jsonify({"error": "Invalid filename"}), 400

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": f"File not found: {filename}"}), 404

    return send_file(str(file_path), as_attachment=True, download_name=filename)
