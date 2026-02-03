"""
Procedure validator for PRISM.

Cross-validates declared sessions/tasks in project.json against
actual data files on disk, emitting PRISM701-706 issues.
"""

import json
import re
from pathlib import Path
from typing import List, Tuple


def validate_procedure(
    project_path: Path, rawdata_path: Path
) -> List[Tuple[str, str]]:
    """Cross-validate declared sessions/tasks against data on disk.

    Args:
        project_path: Path to the project root (containing project.json)
        rawdata_path: Path to the rawdata/ directory being validated

    Returns:
        List of (severity, message) tuples compatible with runner.py issues format.
    """
    issues: List[Tuple[str, str]] = []

    project_json_path = project_path / "project.json"
    if not project_json_path.exists():
        return issues

    try:
        with open(project_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return issues

    sessions = data.get("Sessions", [])
    task_defs = data.get("TaskDefinitions", {})

    # PRISM706: Sessions array is empty
    if not sessions:
        issues.append(("INFO", "PRISM706: Sessions array is empty — no procedure defined yet"))
        return issues

    # Build declared set: {(ses_id, task_name)}
    declared = set()
    declared_sessions = set()
    for s in sessions:
        sid = s.get("id", "")
        declared_sessions.add(sid)
        for t in s.get("tasks", []):
            task_name = t.get("task", "")
            if task_name:
                declared.add((sid, task_name))

                # PRISM705: Task references undefined TaskDefinition
                if task_name not in task_defs:
                    issues.append((
                        "ERROR",
                        f"PRISM705: Task '{task_name}' in {sid} references "
                        f"undefined TaskDefinition",
                    ))

    # Build on-disk set by scanning rawdata/
    disk_set = set()
    disk_sessions = set()

    if rawdata_path.is_dir():
        for sub_dir in rawdata_path.iterdir():
            if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                continue
            for item in sub_dir.iterdir():
                if not item.is_dir():
                    continue
                if item.name.startswith("ses-"):
                    ses_id = item.name
                    disk_sessions.add(ses_id)
                    for mod_dir in item.iterdir():
                        if not mod_dir.is_dir():
                            continue
                        for f in mod_dir.iterdir():
                            if f.is_file() and "_task-" in f.name:
                                m = re.search(
                                    r"_task-([^_]+)", f.name
                                )
                                if m:
                                    disk_set.add((ses_id, m.group(1)))

    # PRISM701: Session on disk not declared in project.json
    for ses_id in sorted(disk_sessions - declared_sessions):
        issues.append((
            "WARNING",
            f"PRISM701: Session '{ses_id}' exists on disk but is not "
            f"declared in project.json Sessions",
        ))

    # PRISM702: Declared session has no data on disk
    for ses_id in sorted(declared_sessions - disk_sessions):
        issues.append((
            "WARNING",
            f"PRISM702: Session '{ses_id}' is declared in project.json "
            f"but has no data on disk",
        ))

    # PRISM703: Task on disk not declared in session
    for ses_id, task_name in sorted(disk_set - declared):
        # Only report if the session itself is declared (otherwise PRISM701 covers it)
        if ses_id in declared_sessions:
            issues.append((
                "WARNING",
                f"PRISM703: Task '{task_name}' in {ses_id} exists on disk "
                f"but is not declared in the session",
            ))

    # PRISM704: Declared non-optional task has no data on disk
    for s in sessions:
        sid = s.get("id", "")
        # Only check if session has data on disk at all
        if sid not in disk_sessions:
            continue
        for t in s.get("tasks", []):
            task_name = t.get("task", "")
            optional = t.get("optional", False)
            if not optional and (sid, task_name) not in disk_set:
                issues.append((
                    "WARNING",
                    f"PRISM704: Non-optional task '{task_name}' in {sid} "
                    f"is declared but has no data on disk",
                ))

    return issues
