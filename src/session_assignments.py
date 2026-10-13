"""Per-response session decisions for repeated LimeSurvey exports.

Spec: docs/superpowers/specs/2026-10-12-session-assignment-review-design.md

``code/session_assignments.json`` maps a LimeSurvey response ``id`` to
``{"skip": true}`` or ``{"session": "<label>"}``. Keyed by response id so the
decisions survive re-exports. Labels are free-form strings: only surrounding
whitespace is stripped, nothing is padded or coerced.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FILE = Path("code") / "session_assignments.json"


class SessionAssignmentError(ValueError):
    """Anything wrong with the decisions file or a requested change."""


def _path(project_path: str | Path) -> Path:
    root = Path(project_path).expanduser()
    return (root.parent if root.is_file() else root) / FILE


def _clean(raw: object, where: str) -> dict[str, dict]:
    responses = raw.get("responses") if isinstance(raw, dict) else None
    if not isinstance(responses, dict):
        raise SessionAssignmentError(f"{where} must hold an object under 'responses'")
    clean: dict[str, dict] = {}
    for response_id, decision in responses.items():
        key = str(response_id).strip()
        if not key or not isinstance(decision, dict):
            raise SessionAssignmentError(f"{where}: bad entry for {response_id!r}")
        if decision == {"skip": True}:
            clean[key] = {"skip": True}
        elif set(decision) == {"session"} and isinstance(decision["session"], str) and decision["session"].strip():
            clean[key] = {"session": decision["session"].strip()}
        else:
            raise SessionAssignmentError(
                f"{where}: entry for {key!r} must be {{'skip': true}} or {{'session': '<label>'}}"
            )
    return clean


def load_session_assignments(project_path: str | Path) -> dict[str, dict]:
    path = _path(project_path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionAssignmentError(f"{path} could not be read: {exc}") from exc
    return _clean(raw, str(path))


def _save(project_path: str | Path, responses: dict[str, dict]) -> None:
    path = _path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = {"version": 1, "responses": responses}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def set_assignment(
    project_path: str | Path,
    response_id: str,
    *,
    skip: bool = False,
    session: str | None = None,
) -> dict[str, dict]:
    label = (session or "").strip()
    if skip == bool(label):  # neither, or both
        raise SessionAssignmentError("Give exactly one of --skip or a non-empty --session label")
    key = str(response_id).strip()
    if not key:
        raise SessionAssignmentError("The response id must not be empty")
    responses = load_session_assignments(project_path)
    responses[key] = {"skip": True} if skip else {"session": label}
    _save(project_path, responses)
    return responses


def unset_assignment(project_path: str | Path, response_id: str) -> dict[str, dict]:
    responses = load_session_assignments(project_path)
    key = str(response_id).strip()
    if key not in responses:
        raise SessionAssignmentError(f"No decision stored for response {key!r}")
    del responses[key]
    _save(project_path, responses)
    return responses
