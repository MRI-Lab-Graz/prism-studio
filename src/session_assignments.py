"""Per-response session decisions for repeated LimeSurvey exports.

Spec: docs/superpowers/specs/2026-10-12-session-assignment-review-design.md

``code/session_assignments.json`` maps, per survey, a LimeSurvey response ``id``
to ``{"skip": true}``, ``{"session": "<label>"}`` or ``{"include": true}``
(take an incomplete response into the automatic numbering):
``{"version": 2, "surveys": {"<survey id>": {"responses": {"2": {"skip": true}}}}}``.
LimeSurvey numbers responses 1..N per survey, so decisions are scoped by the
survey id of the ``.lsa`` (``"default"`` for every other file). Keyed by
response id so the decisions survive re-exports. Labels are free-form strings: only surrounding
whitespace is stripped, nothing is padded or coerced.
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

FILE = Path("code") / "session_assignments.json"


class SessionAssignmentError(ValueError):
    """Anything wrong with the decisions file or a requested change."""


def _path(project_path: str | Path) -> Path:
    root = Path(project_path).expanduser()
    return (root.parent if root.is_file() else root) / FILE


DEFAULT_SURVEY = "default"
_SURVEY_MEMBER = re.compile(r"(?:^|/)survey_(\d+)(?:_responses)?\.(?:lss|lsr)$")


def survey_id_of(path: str | Path) -> str:
    """LimeSurvey survey id from an .lsa's member names; "default" for anything else."""
    path = Path(path)
    if path.suffix.lower() != ".lsa":
        return DEFAULT_SURVEY
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                match = _SURVEY_MEMBER.search(name)
                if match:
                    return match.group(1)
    except (OSError, zipfile.BadZipFile):
        pass
    return DEFAULT_SURVEY


def _clean(responses: object, where: str) -> dict[str, dict]:
    if not isinstance(responses, dict):
        raise SessionAssignmentError(f"{where} must hold an object under 'responses'")
    clean: dict[str, dict] = {}
    for response_id, decision in responses.items():
        key = str(response_id).strip()
        if not key or not isinstance(decision, dict):
            raise SessionAssignmentError(f"{where}: bad entry for {response_id!r}")
        if decision == {"skip": True}:
            clean[key] = {"skip": True}
        elif decision == {"include": True}:
            clean[key] = {"include": True}
        elif set(decision) == {"session"} and isinstance(decision["session"], str) and decision["session"].strip():
            clean[key] = {"session": decision["session"].strip()}
        else:
            raise SessionAssignmentError(
                f"{where}: entry for {key!r} must be {{'skip': true}}, {{'include': true}} or {{'session': '<label>'}}"
            )
    return clean


def _read_all(project_path: str | Path) -> dict[str, dict[str, dict]]:
    """Every survey's cleaned decisions: {survey_id: {response_id: decision}}."""
    path = _path(project_path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionAssignmentError(f"{path} could not be read: {exc}") from exc
    if isinstance(raw, dict) and "responses" in raw and "surveys" not in raw:
        raise SessionAssignmentError(
            f"{path} uses the old format (one list for all surveys); "
            "delete it and save the decisions again"
        )
    surveys = raw.get("surveys") if isinstance(raw, dict) else None
    if not isinstance(surveys, dict):
        raise SessionAssignmentError(f"{path} must hold an object under 'surveys'")
    out: dict[str, dict[str, dict]] = {}
    for survey_id, entry in surveys.items():
        responses = entry.get("responses") if isinstance(entry, dict) else None
        out[str(survey_id)] = _clean(responses, f"{path} (survey {survey_id})")
    return out


def load_session_assignments(project_path: str | Path, survey_id: str = DEFAULT_SURVEY) -> dict[str, dict]:
    return _read_all(project_path).get(str(survey_id), {})


def _save(project_path: str | Path, surveys: dict[str, dict[str, dict]]) -> None:
    path = _path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = {
        "version": 2,
        "surveys": {sid: {"responses": r} for sid, r in surveys.items() if r},
    }
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def set_assignment(
    project_path: str | Path,
    response_id: str,
    *,
    survey_id: str = DEFAULT_SURVEY,
    skip: bool = False,
    session: str | None = None,
    include: bool = False,
) -> dict[str, dict]:
    label = (session or "").strip()
    if [bool(skip), bool(include), bool(label)].count(True) != 1:
        raise SessionAssignmentError(
            "Give exactly one of --skip, --include or a non-empty --session label"
        )
    key = str(response_id).strip()
    if not key:
        raise SessionAssignmentError("The response id must not be empty")
    surveys = _read_all(project_path)
    responses = surveys.setdefault(str(survey_id), {})
    responses[key] = (
        {"skip": True} if skip else {"include": True} if include else {"session": label}
    )
    _save(project_path, surveys)
    return responses


def unset_assignment(
    project_path: str | Path, response_id: str, *, survey_id: str = DEFAULT_SURVEY
) -> dict[str, dict]:
    surveys = _read_all(project_path)
    responses = surveys.get(str(survey_id), {})
    key = str(response_id).strip()
    if key not in responses:
        raise SessionAssignmentError(f"No decision stored for response {key!r}")
    del responses[key]
    _save(project_path, surveys)
    return responses
