"""Biosample routes: thin adapters over `prism_tools biosample template|import` (THE RULE, CLAUDE.md)."""

import dataclasses
import io
import tempfile
from pathlib import Path

from flask import jsonify, request, send_file, session
from werkzeug.utils import secure_filename

from src.biosample_import import import_biosample
from src.biosample_template import write_biosample_template


def api_biosample_import():
    """Run `biosample import` on the uploaded file and the current project; return its ImportResult."""
    upload = request.files.get("file")
    filename = secure_filename(getattr(upload, "filename", "") or "")
    if not filename:
        return jsonify({"error": "No file uploaded"}), 400
    project = (request.form.get("project_path") or session.get("current_project_path") or "").strip()
    if not project:  # the CLI's --project is required
        return jsonify({"error": "No project selected. Load a project before importing biosamples."}), 400
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename  # the original name: messages name the file as the CLI does
        upload.save(path)
        result = import_biosample(
            path, Path(project),
            request.form.get("specimen") or None,
            request.form.get("overwrite") == "true",
            request.form.get("dry_run") == "true",
        )
    return jsonify(dataclasses.asdict(result))


def api_biosample_template():
    """Serve `biosample template` output."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "biosample_template.xlsx"
        write_biosample_template(path)
        data = io.BytesIO(path.read_bytes())
    return send_file(data, as_attachment=True, download_name="biosample_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
