"""Thin Flask adapter over src.item_map (the rule lives there; CLI: `survey item-map`)."""

import json
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from src import item_map

from .tools_helpers import _resolve_requested_or_current_project_root

item_map_bp = Blueprint("item_map", __name__)


def _run(action):
    """Save the upload to a temp dir, read its columns, call ``action(root, columns, name)``."""
    root = _resolve_requested_or_current_project_root(request.form.get("project_path"))
    upload = request.files.get("file")
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    if upload is None or not upload.filename:
        return jsonify({"error": "No survey file uploaded"}), 400
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / Path(upload.filename).name
            upload.save(path)
            return jsonify(action(root, item_map.read_survey_columns(path), upload.filename))
    except (OSError, ValueError) as exc:  # ItemMapError is a ValueError
        return jsonify({"error": str(exc)}), 400


def _announce(name, task="", extra=""):
    task = f" --task {task}" if task else ""
    print(f"[PRISM] CLI equivalent: python prism_tools.py survey item-map --input {name} --project <project>{task}{extra}")


@item_map_bp.route("/api/item-map/suggest", methods=["POST"])
def api_item_map_suggest():
    task = request.form.get("task") or None

    def action(root, columns, name):
        _announce(name, task)
        if not task:
            return {"tasks": item_map.tasks_needing_map(root, columns)}
        return item_map.suggest_for_project(root, task, columns)

    return _run(action)


@item_map_bp.route("/api/item-map", methods=["POST"])
def api_item_map_save():
    task = request.form.get("task")
    accept = request.form.get("accept") == "1"

    def action(root, columns, name):
        try:
            choices = json.loads(request.form.get("choices") or "{}")
        except ValueError as exc:
            raise item_map.ItemMapError(f"choices is not valid JSON: {exc}") from exc
        if not isinstance(choices, dict):
            raise item_map.ItemMapError("choices must be an object of item to column")
        sets = "".join(f" --set {k}={v}" for k, v in choices.items())
        _announce(name, task, (" --accept" if accept else "") + sets)
        path = item_map.apply_choices(root, task, columns, choices, accept)
        return {"ok": True, "path": path.relative_to(root).as_posix() if path else None}

    return _run(action)
