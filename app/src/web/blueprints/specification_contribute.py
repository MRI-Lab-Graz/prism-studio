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
    add_local_values,
    find_unknown_metrics,
    find_unknown_values,
    list_local_items,
    load_local_patches,
    proposal_for_local_terms,
    remove_local_terms,
    remove_local_values,
)
from src.specification import current_specification

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
        "unknown_values": find_unknown_values(project),
        "fields": current_specification().patchable_fields("biosample"),
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


def _values_change(operation):
    """Add or remove values of one field: both routes take {"field": str, "values": [str, ...]}."""
    project = _project()
    if project is None:
        return _error("Open a project first")
    body = _body()
    field, values = body.get("field"), body.get("values")
    if not (isinstance(field, str) and field and isinstance(values, list) and values and all(isinstance(v, str) for v in values)):
        return _error('Give "field" and a non-empty list "values" of strings')
    try:
        result = operation(project, field, values)
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, "written": str(result["written"]) if result["written"] else None, "skipped": result.get("skipped", [])})


@specification_contribute_bp.route("/api/spec/local/add-values", methods=["POST"])
def add_values():
    return _values_change(add_local_values)


@specification_contribute_bp.route("/api/spec/local/remove-values", methods=["POST"])
def remove_values():
    return _values_change(remove_local_values)


@specification_contribute_bp.route("/api/spec/propose", methods=["POST"])
def propose():
    project = _project()
    if project is None:
        return _error("Open a project first")
    body = _body()
    patch = body.get("patch", False)
    if not isinstance(patch, bool):
        return _error('"patch" must be true or false')
    if body.get("all") is True:
        ids = None
    elif patch and not any(k in body for k in ("id", "ids")):
        ids = []  # the schema additions alone
    elif isinstance(body.get("ids"), list) and body["ids"] and all(isinstance(i, str) and i for i in body["ids"]):
        ids = body["ids"]
    elif isinstance(body.get("id"), str) and body["id"]:
        ids = [body["id"]]
    else:
        return _error('Give "id", a non-empty list "ids", "all": true, or "patch": true')
    try:
        if patch and not load_local_patches(project)[0]:
            return _error("This project has no schema additions to share")
        result = proposal_for_local_terms(project, ids, include_patch=patch or body.get("all") is True)
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, **result})
