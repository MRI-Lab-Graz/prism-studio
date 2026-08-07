"""File Management-related prism_tools command handlers.

Mirrors the Studio GUI's File Management page (app/src/web/blueprints/
tools.py's /api/file-management/* routes), which is otherwise entirely
GUI-only. See docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.bids_file_deleter import BidsFileDeleter

_LOG_PREFIXES = {
    "error": "✗",
    "warning": "⚠",
    "success": "✓",
    "step": "→",
}


def _parse_entity_filters(raw_filters: list[str] | None) -> dict[str, str]:
    filters: dict[str, str] = {}
    for item in raw_filters or []:
        if "=" not in item:
            print(f"Error: --entity-filter must be key=value, got: {item}")
            sys.exit(1)
        key, _, value = item.partition("=")
        filters[key.strip()] = value.strip()
    return filters


def _parse_subjects(raw_subjects: str | None) -> list[str] | None:
    if not raw_subjects:
        return None
    return [s.strip() for s in raw_subjects.split(",") if s.strip()]


def cmd_file_management_delete_files(args) -> None:
    """Preview or apply deletion of project files matching BIDS entity
    filters — the CLI equivalent of the Studio GUI's File Management ->
    Delete Files action (BidsFileDeleter, DataLad-aware when the project
    is DataLad-tracked)."""
    as_json = bool(getattr(args, "json", False))
    project_root = Path(args.project).resolve()
    deleter = BidsFileDeleter(project_root)

    modality = args.modality or None
    entity_filters = _parse_entity_filters(args.entity_filter)
    subjects = _parse_subjects(args.subjects)

    try:
        preview = deleter.preview(
            modality=modality, entity_filters=entity_filters, subjects=subjects
        )
    except ValueError as error:
        if as_json:
            print(json.dumps({"success": False, "error": str(error)}, indent=2))
        else:
            print(f"Error: {error}")
        sys.exit(1)

    delete_count = int(preview.get("file_count") or 0)
    if not as_json:
        print(
            f"{delete_count} file(s) matched, "
            f"{len(preview.get('orphaned_root_sidecars', []))} orphaned sidecar(s), "
            f"{len(preview.get('empty_dirs_to_remove', []))} empty directory/directories after deletion."
        )

    if not getattr(args, "apply", False):
        if as_json:
            print(json.dumps({"success": True, "applied": False, **preview}, indent=2))
        else:
            print("Preview only — pass --apply to delete. Files matched:")
            for entry in preview.get("files", [])[:50]:
                print(f"  {entry}")
        return

    if delete_count == 0:
        if as_json:
            print(json.dumps({"success": True, "applied": False, **preview}, indent=2))
        else:
            print(f"No files match the given filters in {project_root}.")
        return

    if not getattr(args, "yes", False) and not as_json:
        confirmation = (
            input(f"Delete {delete_count} file(s) in {project_root}? [y/N] ")
            .strip()
            .lower()
        )
        if confirmation not in {"y", "yes"}:
            print("Aborted.")
            return

    try:
        result = deleter.apply(
            modality=modality, entity_filters=entity_filters, subjects=subjects
        )
    except ValueError as error:
        if as_json:
            print(json.dumps({"success": False, "error": str(error)}, indent=2))
        else:
            print(f"Error: {error}")
        sys.exit(1)

    if as_json:
        print(json.dumps({"success": True, **result}, indent=2))
    else:
        print(
            f"Done: {result.get('deleted_count', 0)} file(s), "
            f"{result.get('deleted_sidecars', 0)} sidecar(s), "
            f"{result.get('removed_empty_dirs', 0)} empty directory/directories removed."
        )
