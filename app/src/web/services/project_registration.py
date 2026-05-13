"""Project registration services for web conversion workflows."""

from pathlib import Path
import json
from typing import Any

from src.utils.naming import sanitize_id


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
    text = sanitize_id(str(session_id or "").strip())
    if not text:
        return None
    if text.lower() == "nan":
        return None

    label = text[4:] if text[:4].lower() == "ses-" else text
    label = "".join(ch for ch in label if ch.isalnum())
    if not label:
        return None
    return f"ses-{label}"


def _normalize_run_value(run_value: Any) -> str | None:
    if run_value in {None, ""}:
        return None
    text = str(run_value).strip()
    if not text:
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = "".join(ch for ch in label if ch.isalnum())
    if not label:
        return None
    return f"run-{label}"


def _normalize_template_version_selections(
    raw_overrides: Any,
    *,
    default_session: str | None,
) -> list[dict[str, Any]]:
    """Normalize template-version payloads to task/session/run/version entries."""
    normalized: list[dict[str, Any]] = []

    def _append_entry(
        *,
        task: Any,
        version_payload: Any,
        session_value: Any = None,
        run_value: Any = None,
    ) -> None:
        task_name = str(task or "").strip().lower()
        version_name = _coerce_version_value(version_payload)
        if not task_name or not version_name:
            return

        session_name = _normalize_session_id(
            str(session_value).strip()
            if session_value not in {None, ""}
            else default_session
        )
        run_entity = _normalize_run_value(run_value)

        entry: dict[str, Any] = {
            "task": task_name,
            "version": version_name,
        }
        if session_name:
            entry["session"] = session_name
        if run_entity is not None:
            entry["run"] = run_entity
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

    deduped: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
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
            key=lambda item: (item[0], item[1] or "", item[2] or ""),
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
    """Persist template version selections without writing session provenance."""
    if not session_id:
        return

    pj_path = project_path / "project.json"
    if not pj_path.exists():
        return

    try:
        with open(pj_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return

    normalized_session_id = _normalize_session_id(session_id)
    if not normalized_session_id:
        return
    session_id = normalized_session_id

    selection_updates = _normalize_template_version_selections(
        template_version_overrides,
        default_session=session_id,
    )
    if selection_updates:
        existing_selections = _normalize_template_version_selections(
            data.get("TemplateVersionSelections"),
            default_session=None,
        )
        merged: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
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
                key=lambda item: (item[0], item[1] or "", item[2] or ""),
            )
        ]
    else:
        return

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
