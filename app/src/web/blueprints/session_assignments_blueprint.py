"""Thin Flask adapter over src.session_assignments / src.participants_sessions."""

import shutil
from pathlib import Path

from flask import Blueprint, jsonify, request

from src.participants_converter import load_participant_source
from src.participants_sessions import session_assignment_table
from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    survey_id_of,
    unset_assignment,
)

from .conversion_participants_io import (
    _expected_delimiter_for_suffix,
    _normalize_separator_option,
    _resolve_participants_sheet_arg,
    _save_participants_upload_to_temp,
)
from .tools_helpers import _resolve_requested_or_current_project_root

session_assignments_bp = Blueprint("session_assignments", __name__)


@session_assignments_bp.route("/api/session-assignments/review", methods=["POST"])
def api_review_session_assignments():
    requested = request.form.get("project_path")
    root = _resolve_requested_or_current_project_root(requested)
    if str(requested or "").strip() and root is None:
        return jsonify({"error": "The project folder does not exist."}), 400
    id_column = request.form.get("id_column", "").strip()
    if not id_column:
        return jsonify({"error": "Select the participant ID column first."}), 400
    try:
        upload = _save_participants_upload_to_temp(
            uploaded_file=request.files.get("file"),
            temp_prefix="prism_session_review_",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        input_path = Path(str(upload["input_path"]))
        suffix = str(upload["suffix"])
        df, _ = load_participant_source(
            input_path,
            separator=_expected_delimiter_for_suffix(
                suffix, _normalize_separator_option(request.form.get("separator"))
            ),
            sheet=_resolve_participants_sheet_arg(
                input_path=input_path, suffix=suffix, sheet_value=request.form.get("sheet")
            ),
        )
        survey_id = survey_id_of(input_path)
        decisions = load_session_assignments(root, survey_id) if root else {}
        rows, warnings = session_assignment_table(
            df,
            id_column,
            request.form.get("date_column", "").strip() or "startdate",
            decisions=decisions,
            imported_root=root if request.form.get("skip_existing") == "true" else None,
            survey_id=survey_id,
        )
        return jsonify({"survey_id": survey_id, "rows": rows, "warnings": warnings})
    except (ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        shutil.rmtree(str(upload["tmp_dir"]), ignore_errors=True)


@session_assignments_bp.route("/api/session-assignments", methods=["POST"])
def api_set_session_assignment():
    payload = request.get_json(silent=True) or {}
    root = _resolve_requested_or_current_project_root(payload.get("project_path"))
    if root is None:
        return jsonify({"error": "No project selected"}), 400
    response_id = str(payload.get("response_id") or "").strip()
    session = payload.get("session")
    if session is not None and not isinstance(session, str):
        return jsonify({"error": "The session label must be text."}), 400
    survey_id = str(payload.get("survey_id") or "default")
    try:
        if payload.get("clear"):
            responses = unset_assignment(root, response_id, survey_id=survey_id)
        else:
            responses = set_assignment(
                root,
                response_id,
                survey_id=survey_id,
                skip=bool(payload.get("skip")),
                include=bool(payload.get("include")),
                session=session,
            )
    except SessionAssignmentError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "responses": responses})
