"""
NeuroBagel Blueprint for PRISM.
Handles NeuroBagel API routes.
"""

import os
from flask import Blueprint, jsonify, request, current_app
from src.neurobagel import (
    augment_neurobagel_data,
    fetch_neurobagel_participants,
    sample_local_participant_columns,
)

neurobagel_bp = Blueprint("neurobagel", __name__)


@neurobagel_bp.route("/api/neurobagel/participants")
def get_neurobagel_participants():
    """Fetch and return augmented NeuroBagel participants dictionary.

    Uses external URL if available, otherwise falls back to built-in schema.
    All controlled vocabularies are hardcoded in augment_neurobagel_data().
    """
    raw_data = fetch_neurobagel_participants()
    augmented_data = augment_neurobagel_data(raw_data)
    return jsonify(augmented_data)


@neurobagel_bp.route("/api/neurobagel/local-participants")
def get_local_participants():
    """Extract unique values from local participants.tsv for categorical mapping.

    Supports two modes:
    1. Upload mode: ?session_id=xxx (from JSON editor uploads)
    2. Project mode: ?project_path=xxx (from current project in converter)
    """
    session_id = request.args.get("session_id")
    project_path = request.args.get("project_path")

    if not session_id and not project_path:
        return jsonify({"error": "No session ID or project path"}), 400

    # Determine TSV path based on mode
    if project_path:
        # Project mode: use project path directly
        tsv_path = os.path.join(project_path, "participants.tsv")
    else:
        # Upload mode: use session directory
        session_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], session_id)
        tsv_path = os.path.join(session_dir, "participants.tsv")

    try:
        result = sample_local_participant_columns(tsv_path)
        return jsonify({"columns": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
