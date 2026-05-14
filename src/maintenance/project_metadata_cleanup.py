from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.cross_platform import CrossPlatformFile


@dataclass(frozen=True)
class ProjectMetadataCleanupReport:
    project_json_path: Path
    changed: bool
    removed_sessions: int
    removed_task_entries: int
    removed_source_entries: int
    removed_task_definitions: int
    kept_task_definitions: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["project_json_path"] = str(self.project_json_path)
        return payload


@dataclass(frozen=True)
class ProjectMetadataCleanupBatchReport:
    root_path: Path
    processed_projects: int
    changed_projects: int
    removed_sessions: int
    removed_task_entries: int
    removed_source_entries: int
    removed_task_definitions: int
    kept_task_definitions: int
    reports: list[ProjectMetadataCleanupReport]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": str(self.root_path),
            "processed_projects": self.processed_projects,
            "changed_projects": self.changed_projects,
            "removed_sessions": self.removed_sessions,
            "removed_task_entries": self.removed_task_entries,
            "removed_source_entries": self.removed_source_entries,
            "removed_task_definitions": self.removed_task_definitions,
            "kept_task_definitions": self.kept_task_definitions,
            "reports": [report.to_dict() for report in self.reports],
        }


def _resolve_project_json_path(project: str | Path) -> Path:
    candidate = Path(project)
    if candidate.is_dir():
        return candidate / "project.json"
    return candidate


def discover_project_json_files(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if root_path.is_file():
        return [root_path] if root_path.name == "project.json" else []
    if not root_path.exists() or not root_path.is_dir():
        return []
    return sorted(path for path in root_path.rglob("project.json") if path.is_file())


def _count_session_task_entries(sessions: object) -> tuple[int, int, int]:
    if not isinstance(sessions, list):
        return 0, 0, 0

    removed_sessions = len(sessions)
    removed_task_entries = 0
    removed_source_entries = 0

    for session in sessions:
        if not isinstance(session, dict):
            continue
        tasks = session.get("tasks")
        if not isinstance(tasks, list):
            continue
        removed_task_entries += len(tasks)
        for task in tasks:
            if isinstance(task, dict) and "source" in task:
                removed_source_entries += 1

    return removed_sessions, removed_task_entries, removed_source_entries


def cleanup_project_metadata(
    project: str | Path,
    *,
    dry_run: bool = False,
    drop_task_definitions: bool = False,
) -> ProjectMetadataCleanupReport:
    project_json_path = _resolve_project_json_path(project)
    if not project_json_path.exists() or not project_json_path.is_file():
        raise FileNotFoundError(f"project.json not found: {project_json_path}")

    try:
        payload = json.loads(CrossPlatformFile.read_text(str(project_json_path)))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {project_json_path}: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"project.json must contain a JSON object: {project_json_path}")

    sessions = payload.get("Sessions")
    removed_sessions, removed_task_entries, removed_source_entries = (
        _count_session_task_entries(sessions)
    )
    had_sessions_key = "Sessions" in payload
    if had_sessions_key:
        del payload["Sessions"]

    task_definitions = payload.get("TaskDefinitions")
    task_definition_count = len(task_definitions) if isinstance(task_definitions, dict) else 0
    had_task_definitions_key = "TaskDefinitions" in payload
    removed_task_definitions = 0
    kept_task_definitions = task_definition_count
    if drop_task_definitions and had_task_definitions_key:
        del payload["TaskDefinitions"]
        removed_task_definitions = task_definition_count
        kept_task_definitions = 0

    changed = had_sessions_key or (drop_task_definitions and had_task_definitions_key)

    if changed and not dry_run:
        CrossPlatformFile.write_text(
            str(project_json_path),
            json.dumps(payload, indent=2, ensure_ascii=False),
        )

    return ProjectMetadataCleanupReport(
        project_json_path=project_json_path,
        changed=changed,
        removed_sessions=removed_sessions,
        removed_task_entries=removed_task_entries,
        removed_source_entries=removed_source_entries,
        removed_task_definitions=removed_task_definitions,
        kept_task_definitions=kept_task_definitions,
    )


def cleanup_project_metadata_tree(
    root: str | Path,
    *,
    dry_run: bool = False,
    drop_task_definitions: bool = False,
) -> ProjectMetadataCleanupBatchReport:
    root_path = Path(root)
    project_files = discover_project_json_files(root_path)
    if not project_files:
        raise FileNotFoundError(f"No project.json files found under: {root_path}")

    reports = [
        cleanup_project_metadata(
            project_json_path,
            dry_run=dry_run,
            drop_task_definitions=drop_task_definitions,
        )
        for project_json_path in project_files
    ]

    return ProjectMetadataCleanupBatchReport(
        root_path=root_path,
        processed_projects=len(reports),
        changed_projects=sum(1 for report in reports if report.changed),
        removed_sessions=sum(report.removed_sessions for report in reports),
        removed_task_entries=sum(report.removed_task_entries for report in reports),
        removed_source_entries=sum(report.removed_source_entries for report in reports),
        removed_task_definitions=sum(
            report.removed_task_definitions for report in reports
        ),
        kept_task_definitions=sum(report.kept_task_definitions for report in reports),
        reports=reports,
    )