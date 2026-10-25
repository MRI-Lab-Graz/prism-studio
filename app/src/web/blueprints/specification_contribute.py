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
    list_all_local_items,
    load_local_patches,
    proposal_for_local_terms,
    remove_local_terms,
    remove_local_values,
)
from src.spec_contribute import example_entries, proposal_for_new_kind, proposal_for_new_metric, proposal_for_values, spec_catalog

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
    if project is None:  # a message, not a 4xx: the page is opened without a project all the time
        return jsonify({"success": False, "error": "Open a project first"})
    items = list_all_local_items(project)
    if "modality" in request.args:
        items = [i for i in items if i["modality"] == request.args["modality"]]
    return jsonify({
        "success": True,
        "items": items,
        "unknown_metrics": find_unknown_metrics(project),
        "unknown_values": find_unknown_values(project),
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
    modality = body.get("modality", "biosample")
    if not isinstance(modality, str):
        return _error('"modality" must be text')
    try:
        result = operation(project, field, values, modality=modality)
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, "written": str(result["written"]) if result["written"] else None, "skipped": result.get("skipped", [])})


@specification_contribute_bp.route("/api/spec/local/add-values", methods=["POST"])
def add_values():
    return _values_change(add_local_values)


@specification_contribute_bp.route("/api/spec/local/remove-values", methods=["POST"])
def remove_values():
    return _values_change(remove_local_values)


@specification_contribute_bp.route("/api/spec/catalog", methods=["GET"])
def catalog():
    return jsonify({"success": True, **spec_catalog(), "project_open": _project() is not None})


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _context_options(body: dict) -> dict:
    """The "not sure" / entries / closest options of a propose request; spec_contribute validates them."""
    return {"not_sure": body.get("not_sure", False), "entries": body.get("entries"), "closest": body.get("closest")}


@specification_contribute_bp.route("/api/spec/propose-values", methods=["POST"])
def propose_values():
    body = _body()
    modality, field, values = body.get("modality", "biosample"), body.get("field"), body.get("values")
    if not (isinstance(modality, str) and isinstance(field, str) and field and _strings(values)):
        return _error('Give "field" and a list "values" of strings')
    try:
        return jsonify({"success": True, **proposal_for_values(modality, field, values, **_context_options(body))})
    except OverlayError as exc:
        return _error(str(exc))


@specification_contribute_bp.route("/api/spec/propose-metric", methods=["POST"])
def propose_metric():
    body = _body()
    modality, aliases = body.get("modality", "biosample"), body.get("aliases", [])
    texts = [body.get(k) for k in ("name", "description", "units", "specimen")]
    if not (isinstance(modality, str) and _strings(aliases) and all(isinstance(t, str) for t in texts)):
        return _error('Give "name", "description", "units" and "specimen" as text and "aliases" as a list of text')
    try:
        result = proposal_for_new_metric(*texts, aliases=aliases, modality=modality, project_root=_project(), **_context_options(body))
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, **result})


@specification_contribute_bp.route("/api/spec/propose-new-kind", methods=["POST"])
def propose_new_kind():
    body = _body()
    try:
        result = proposal_for_new_kind(body.get("description"), body.get("sample"), body.get("closest"))
    except OverlayError as exc:
        return _error(str(exc))
    if result["problems"]:
        return jsonify({"success": False, "error": "; ".join(result["problems"]), **result}), 400
    return jsonify({"success": True, **result})


@specification_contribute_bp.route("/api/spec/propose", methods=["POST"])
def propose():
    project = _project()
    if project is None:
        return _error("Open a project first")
    body = _body()
    patch = body.get("patch", False)
    if not isinstance(patch, bool):
        return _error('"patch" must be true or false')
    modality = body.get("modality", "biosample")
    if not isinstance(modality, str):
        return _error('"modality" must be text')
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
        if patch and not load_local_patches(project, modality)[0]:
            return _error("This project has no schema additions to share")
        result = proposal_for_local_terms(project, ids, modality=modality, include_patch=patch or body.get("all") is True)
    except OverlayError as exc:
        return _error(str(exc))
    return jsonify({"success": True, **result})


@specification_contribute_bp.route("/api/spec/example", methods=["GET"])
def example():
    try:
        return jsonify({"success": True, **example_entries(request.args.get("modality", ""), request.args.get("template") or None)})
    except OverlayError as exc:
        return _error(str(exc))
