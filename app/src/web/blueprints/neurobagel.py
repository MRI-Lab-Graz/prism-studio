"""
NeuroBagel Blueprint for PRISM.
Handles NeuroBagel API routes.
"""

import os
import json
import pandas as pd
from flask import Blueprint, jsonify, request, current_app
from src.web.neurobagel import fetch_neurobagel_participants, augment_neurobagel_data

neurobagel_bp = Blueprint("neurobagel", __name__)


@neurobagel_bp.route("/api/neurobagel/participants")
def get_neurobagel_participants():
    """Fetch and return augmented NeuroBagel participants dictionary."""
    raw_data = fetch_neurobagel_participants()
    if not raw_data:
        return jsonify({"error": "Could not fetch NeuroBagel data"}), 500

    augmented_data = augment_neurobagel_data(raw_data)
    return jsonify(augmented_data)


@neurobagel_bp.route("/api/neurobagel/local-participants")
def get_local_participants():
    """Extract unique values from local participants.tsv for categorical mapping."""
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "No session ID"}), 400

    session_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], session_id)
    tsv_path = os.path.join(session_dir, "participants.tsv")

    if not os.path.exists(tsv_path):
        return jsonify({"columns": {}})

    try:
        df = pd.read_csv(tsv_path, sep="\t")
        result = {}
        for col in df.columns:
            # Only return unique values for non-ID columns with reasonable number of unique values
            if col.lower() not in ["participant_id", "id"] and df[col].nunique() < 50:
                # Filter out NaNs and convert to strings
                unique_vals = [str(v) for v in df[col].dropna().unique().tolist()]
                result[col] = sorted(unique_vals)

        return jsonify({"columns": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@neurobagel_bp.route("/api/neurobagel/save-json", methods=["POST"])
def save_participants_json():
    """Save the generated participants.json to the session directory."""
    data = request.json
    session_id = data.get("session_id")
    json_content = data.get("content")

    if not session_id or not json_content:
        return jsonify({"error": "Missing session_id or content"}), 400

    session_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], session_id)
    if not os.path.exists(session_dir):
        return jsonify({"error": "Session directory not found"}), 404

    target_path = os.path.join(session_dir, "participants.json")
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(json_content, f, indent=4)
        return jsonify({"success": True, "path": "participants.json"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
