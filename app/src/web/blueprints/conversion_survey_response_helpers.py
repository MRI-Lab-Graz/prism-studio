from typing import Any


def coerce_flask_response(response_value):
    """Normalize a Flask view return value to a response object and status code."""
    response = response_value
    status_code = None
    if isinstance(response_value, tuple):
        response = response_value[0]
        if len(response_value) > 1:
            status_code = response_value[1]
    if status_code is None:
        status_code = getattr(response, "status_code", 200)
    return response, status_code


def build_prepare_workflow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    preview_payload = (
        payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
    )
    prepared_payload: dict[str, Any] = {
        "ok": True,
        "tasks_included": list(payload.get("tasks_included") or []),
        "detected_sessions": list(payload.get("detected_sessions") or []),
        "task_runs": payload.get("task_runs") or {},
        "session_column": payload.get("session_column"),
        "run_column": payload.get("run_column"),
        "multivariant_tasks": payload.get("multivariant_tasks") or {},
        "preview_participants": list(preview_payload.get("participants") or []),
        "applied_value_offsets": payload.get("applied_value_offsets") or {},
        "value_offset_application_counts": payload.get(
            "value_offset_application_counts"
        )
        or {},
        "requires_template_completion": bool(
            payload.get("requires_template_completion")
        ),
    }
    if payload.get("workflow_gate") is not None:
        prepared_payload["workflow_gate"] = payload.get("workflow_gate")
    if payload.get("near_match_applied"):
        prepared_payload["near_match_applied"] = True
    return prepared_payload


def format_value_offset_confirmation_response(
    error: Exception,
    log_messages: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    task = str(getattr(error, "task", "") or "").strip().lower()
    item_id = str(getattr(error, "item_id", "") or "").strip()
    raw_value = getattr(error, "raw_value", None)
    subject_id = str(getattr(error, "sub_id", "") or "").strip()
    expected_levels = list(getattr(error, "expected_levels", []) or [])

    suggested_offsets: list[float | int] = []
    for raw_offset in list(getattr(error, "suggested_offsets", []) or []):
        try:
            numeric = float(raw_offset)
        except (TypeError, ValueError):
            continue
        rounded = round(numeric)
        if abs(numeric - rounded) < 1e-9:
            suggested_offsets.append(int(rounded))
        else:
            suggested_offsets.append(round(numeric, 6))
    suggested_offset_labels = [f"{float(offset):+g}" for offset in suggested_offsets]

    configured_offset = getattr(error, "configured_offset", None)
    adjusted_value = getattr(error, "adjusted_value", None)
    raw_value_valid_without_offset = getattr(
        error, "raw_value_valid_without_offset", None
    )
    offset_evidence = getattr(error, "offset_evidence", None)
    evidence_classification = ""
    if isinstance(offset_evidence, dict):
        evidence_classification = str(
            offset_evidence.get("classification") or ""
        ).strip().lower()

    fallback_message = (
        "Survey values are outside template levels. Review and fix out-of-range source values before continuing."
    )
    review_message = str(error).strip() or fallback_message
    if configured_offset is None and evidence_classification in {
        "item_issues_likely",
        "structural_offset_likely",
    }:
        if evidence_classification == "structural_offset_likely":
            review_message = (
                "Sampled out-of-range values may reflect a task-wide shifted scale, but this is not proof."
            )
        else:
            review_message = (
                "Sampled out-of-range values do not support treating this as a task-wide scale shift."
            )
    if configured_offset is not None:
        review_message += (
            " Fix the data in the input data or (if you are really confident) rescale, then run Preview again."
            " Use Advanced options only when you can independently confirm a full-task shifted scale."
            " Manual task value offsets are applied to observed numeric input values (value + offset), not to template scale definitions."
        )
        if suggested_offset_labels:
            review_message += (
                " Sample-based offset hint(s): "
                + ", ".join(suggested_offset_labels)
                + "."
            )
        if raw_value_valid_without_offset is True:
            review_message += (
                " This sampled value is already valid without offset;"
                " the configured offset direction is likely wrong for this template/data pairing."
                " Verify offset direction and template version selection."
            )
    else:
        review_message += (
            " Required first: fix out-of-range values in the input data, then run Preview again."
            " Advanced-only fallback: use a manual task value offset only with independent evidence of a full-task scale shift (for example, every item is 1-4 while the template is 0-3)."
            " Manual task value offsets are applied to observed numeric input values (value + offset), not to template scale definitions."
            " Do not use offsets to bypass item-level data errors."
        )
    payload: dict[str, Any] = {
        "error": "value_offset_manual_review_required",
        "message": review_message,
        "task": task,
        "item_id": item_id,
        "raw_value": raw_value,
        "expected_levels": expected_levels,
        "suggested_offsets": suggested_offsets,
    }
    if subject_id:
        payload["subject_id"] = subject_id
    if configured_offset is not None:
        payload["configured_offset"] = configured_offset
    if adjusted_value is not None:
        payload["adjusted_value"] = adjusted_value
    if isinstance(raw_value_valid_without_offset, bool):
        payload["raw_value_valid_without_offset"] = raw_value_valid_without_offset
    if isinstance(offset_evidence, dict):
        payload["offset_evidence"] = offset_evidence
    payload["manual_action"] = "advanced_value_offsets"
    if log_messages is not None:
        payload["log"] = log_messages
    return payload


def format_unmatched_groups_response(
    unmatched_groups_error,
    non_item_toplevel_keys: set[str],
    log_messages: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build the JSON response dict for an UnmatchedGroupsError."""

    def _safe_prism_json(value):
        if isinstance(value, dict):
            return value
        return {}

    payload = {
        "error": "unmatched_groups",
        "message": str(unmatched_groups_error),
        "unmatched": [
            {
                "group_name": group["group_name"],
                "task_key": group["task_key"],
                "item_count": len(
                    [
                        key
                        for key in _safe_prism_json(group.get("prism_json"))
                        if key not in non_item_toplevel_keys
                        and isinstance(
                            _safe_prism_json(group.get("prism_json")).get(key), dict
                        )
                    ]
                ),
                "item_codes": sorted(group.get("item_codes", []))[:10],
                "prism_json": _safe_prism_json(group.get("prism_json")),
            }
            for group in unmatched_groups_error.unmatched
        ],
    }
    if log_messages is not None:
        payload["log"] = log_messages
    return payload