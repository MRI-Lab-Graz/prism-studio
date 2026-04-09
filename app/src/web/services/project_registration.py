"""Project registration services for web conversion workflows."""

from pathlib import Path
import json
from typing import Any


def _coerce_version_value(raw_value: Any) -> str:
    """Collapse payload values into a concrete version string."""
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, dict):
        nested = raw_value.get("version")
        if nested is not None:
            nested_version = _coerce_version_value(nested)
            if nested_version:
                return nested_version
        for lang in ("en", "de"):
            candidate = raw_value.get(lang)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in raw_value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _normalize_session_id(session_id: str | None) -> str | None:
    text = str(session_id or "").strip()
    if not text:
        return None

    if not text.lower().startswith("ses-"):
        text = f"ses-{text}"

    text = f"ses-{text[4:]}"
    num_part = text[4:]
    try:
        num_value = int(num_part)
        return f"ses-{num_value:02d}"
    except ValueError:
        return f"ses-{num_part.lower()}"


def _normalize_run_value(run_value: Any) -> int | None:
    if run_value in {None, ""}:
        return None
    try:
        parsed = int(str(run_value).strip())
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _normalize_template_version_selections(
    raw_overrides: Any,
    *,
    default_session: str | None,
) -> list[dict[str, Any]]:
    """Normalize template-version payloads to task/session/run/version entries."""
    normalized: list[dict[str, Any]] = []

    def _append_entry(
        *, task: Any, version_payload: Any, session_value: Any = None, run_value: Any = None
    ) -> None:
        task_name = str(task or "").strip().lower()
        version_name = _coerce_version_value(version_payload)
        if not task_name or not version_name:
            return

        session_name = _normalize_session_id(
            str(session_value).strip() if session_value not in {None, ""} else default_session
        )
        run_number = _normalize_run_value(run_value)

        entry: dict[str, Any] = {
            "task": task_name,
            "version": version_name,
        }
        if session_name:
            entry["session"] = session_name
        if run_number is not None:
            entry["run"] = run_number
        normalized.append(entry)

    if isinstance(raw_overrides, dict):
        for task, value in raw_overrides.items():
            if isinstance(value, dict):
                _append_entry(
                    task=task,
                    version_payload=value,
                    session_value=value.get("session"),
                    run_value=value.get("run"),
                )
            else:
                _append_entry(task=task, version_payload=value)
    elif isinstance(raw_overrides, list):
        for entry in raw_overrides:
            if not isinstance(entry, dict):
                continue
            _append_entry(
                task=entry.get("task"),
                version_payload=entry.get("version"),
                session_value=entry.get("session"),
                run_value=entry.get("run"),
            )

    deduped: dict[tuple[str, str | None, int | None], dict[str, Any]] = {}
    for entry in normalized:
        key = (
            entry.get("task", ""),
            entry.get("session"),
            entry.get("run"),
        )
        deduped[key] = entry

    return [
        deduped[key]
        for key in sorted(
            deduped.keys(),
            key=lambda item: (item[0], item[1] or "", item[2] or 0),
        )
    ]


def register_session_in_project(
    project_path: Path,
    session_id: str,
    tasks: list,
    modality: str,
    source_file: str,
    converter: str,
    template_version_overrides: Any = None,
) -> None:
    """Register conversion output in project.json Sessions/TaskDefinitions."""
    if not session_id or not tasks:
        return

    pj_path = project_path / "project.json"
    if not pj_path.exists():
        return

    try:
        with open(pj_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return

    if "Sessions" not in data:
        data["Sessions"] = []
    if "TaskDefinitions" not in data:
        data["TaskDefinitions"] = {}

    normalized_session_id = _normalize_session_id(session_id)
    if not normalized_session_id:
        return
    session_id = normalized_session_id

    target = None
    for session in data["Sessions"]:
        if session.get("id") == session_id:
            target = session
            break

    if target is None:
        target = {"id": session_id, "label": session_id, "tasks": []}
        data["Sessions"].append(target)

    if "tasks" not in target:
        target["tasks"] = []

    from datetime import date

    today = date.today().isoformat()
    source_obj = {
        "file": source_file,
        "converter": converter,
        "convertedAt": today,
    }

    for task_name in tasks:
        existing = next(
            (task for task in target["tasks"] if task.get("task") == task_name), None
        )
        if existing:
            existing["source"] = source_obj
        else:
            target["tasks"].append({"task": task_name, "source": source_obj})

        if task_name not in data["TaskDefinitions"]:
            data["TaskDefinitions"][task_name] = {"modality": modality}

    selection_updates = _normalize_template_version_selections(
        template_version_overrides,
        default_session=session_id,
    )
    if selection_updates:
        existing_selections = _normalize_template_version_selections(
            data.get("TemplateVersionSelections"),
            default_session=None,
        )
        merged: dict[tuple[str, str | None, int | None], dict[str, Any]] = {}
        for entry in existing_selections + selection_updates:
            key = (
                entry.get("task", ""),
                entry.get("session"),
                entry.get("run"),
            )
            merged[key] = entry
        data["TemplateVersionSelections"] = [
            merged[key]
            for key in sorted(
                merged.keys(),
                key=lambda item: (item[0], item[1] or "", item[2] or 0),
            )
        ]

    try:
        from src.cross_platform import CrossPlatformFile
    except ImportError:
        from cross_platform import CrossPlatformFile

    try:
        CrossPlatformFile.write_text(
            str(pj_path), json.dumps(data, indent=2, ensure_ascii=False)
        )
    except Exception:
        return
