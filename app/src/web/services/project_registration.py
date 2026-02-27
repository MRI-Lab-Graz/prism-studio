"""Project registration services for web conversion workflows."""

from pathlib import Path
import json


def register_session_in_project(
    project_path: Path,
    session_id: str,
    tasks: list,
    modality: str,
    source_file: str,
    converter: str,
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

    if not session_id.startswith("ses-"):
        session_id = f"ses-{session_id}"

    num_part = session_id[4:]
    try:
        session_num = int(num_part)
        session_id = f"ses-{session_num:02d}"
    except ValueError:
        pass

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
