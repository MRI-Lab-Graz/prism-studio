"""Thin Flask adapter over src.session_map (the rule lives there)."""

from flask import Blueprint, jsonify, request

from src.session_map import (
    SessionMapError,
    load_session_map,
    project_timepoints,
    set_session_entries,
)

from .tools_helpers import _resolve_requested_or_current_project_root

session_map_bp = Blueprint("session_map", __name__)


@session_map_bp.route("/api/session-map", methods=["GET"])
def api_get_session_map():
    root = _resolve_requested_or_current_project_root(request.args.get("project_path"))
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    try:
        return jsonify(
            {
                "ok": True,
                "timepoints": project_timepoints(root),
                "map": load_session_map(root),
            }
        )
    except SessionMapError as exc:
        return jsonify({"error": str(exc)}), 400


@session_map_bp.route("/api/session-map", methods=["POST"])
def api_set_session_map():
    payload = request.get_json(silent=True) or {}
    root = _resolve_requested_or_current_project_root(payload.get("project_path"))
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    entries = payload.get("entries")
    if not isinstance(entries, dict) or not entries:
        return (
            jsonify(
                {"error": "entries must be a non-empty object of label to session name"}
            ),
            400,
        )
    try:
        return jsonify({"ok": True, "map": set_session_entries(root, entries)})
    except SessionMapError as exc:
        return jsonify({"error": str(exc)}), 400
