"""Routes of the Contribute page (specification: local metrics and sharing them).

Thin adapters over src.spec_overlay, the same functions the `prism_tools.py spec` commands run. The page
decides nothing and sends nothing: sharing is a link to the prefilled form, opened by the user.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, session

from src.spec_overlay import (
    OverlayError,
    add_local_term,
    find_unknown_metrics,
    list_local_items,
    proposal_for_local_term,
    remove_local_terms,
)

specification_contribute_bp = Blueprint("specification_contribute", __name__)


def _project() -> Path | None:
    path = str(session.get("current_project_path", "") or "").strip()
    return Path(path) if path and os.path.isdir(path) else None


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@specification_contribute_bp.route("/api/spec/local", methods=["GET"])
def list_local():
    project = _project()
    if project is None:
        return _error("Open a project first")
    return jsonify({
        "success": True,
        "items": list_local_items(project),
        "unknown_metrics": find_unknown_metrics(project),
    })


@specification_contribute_bp.route("/api/spec/local/add-term", methods=["POST"])
def add_term():
    project = _project()
    if project is None:
        return _error("Open a project first")
    data = _body()
    column, data_file, label = data.get("column"), data.get("data_file"), data.get("label")
    if not (isinstance(column, str) and column and isinstance(data_file, str) and data_file):
        return _error("A column and a data file are required")
    if not Path(data_file).resolve().is_relative_to(project.resolve()):
        return _error("The data file must be inside the project")
    try:
        result = add_local_term(
            project, column=column, data_file=data_file, label=label if isinstance(label, str) and label else None
        )
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, "proposal": result["proposal"], "written": [str(p) for p in result["written"]]})


@specification_contribute_bp.route("/api/spec/local/remove", methods=["POST"])
def remove_term():
    project = _project()
    if project is None:
        return _error("Open a project first")
    try:
        removed = remove_local_terms(project, "biosample", str(_body().get("id") or ""))
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, "removed": [str(p) for p in removed]})


@specification_contribute_bp.route("/api/spec/propose", methods=["POST"])
def propose():
    project = _project()
    if project is None:
        return _error("Open a project first")
    try:
        result = proposal_for_local_term(project, str(_body().get("id") or ""))
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, **result})
