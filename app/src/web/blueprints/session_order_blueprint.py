"""Thin Flask adapter over src.session_order (the rule lives there)."""

import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from src.session_map import SessionMapError, project_session_labels
from src.session_order import (
    import_session_order,
    load_session_order,
    remove_order_entries,
    set_order_entries,
)

from .tools_helpers import _resolve_requested_or_current_project_root

session_order_bp = Blueprint("session_order", __name__)


def _root(requested):
    root = _resolve_requested_or_current_project_root(requested)
    if root is None:
        return None, (jsonify({"error": "No project selected"}), 400)
    return root, None


@session_order_bp.route("/api/session-order", methods=["GET"])
def api_get_session_order():
    root, error = _root(request.args.get("project_path"))
    if error:
        return error
    try:
        return jsonify(
            {"ok": True, "session_labels": project_session_labels(root), "order": load_session_order(root)}
        )
    except SessionMapError as exc:
        return jsonify({"error": str(exc)}), 400


@session_order_bp.route("/api/session-order", methods=["POST"])
def api_set_session_order():
    payload = request.get_json(silent=True) or {}
    root, error = _root(payload.get("project_path"))
    if error:
        return error
    participant = str(payload.get("participant") or "").strip()
    number = str(payload.get("number") or "").strip()
    try:
        if payload.get("clear"):
            order = remove_order_entries(root, participant, [number] if number else None)
        else:
            order = set_order_entries(root, participant, {number: payload.get("session")})
        return jsonify({"ok": True, "order": order})
    except SessionMapError as exc:
        return jsonify({"error": str(exc)}), 400


@session_order_bp.route("/api/session-order/import", methods=["POST"])
def api_import_session_order():
    root, error = _root(request.form.get("project_path"))
    if error:
        return error
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose the prepared session order file."}), 400
    with tempfile.TemporaryDirectory(prefix="prism_session_order_") as tmp:
        path = Path(tmp) / f"order{Path(upload.filename).suffix.lower()}"
        upload.save(path)
        try:
            order = import_session_order(root, path, replace=request.form.get("replace") == "true")
        except SessionMapError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "order": order})
