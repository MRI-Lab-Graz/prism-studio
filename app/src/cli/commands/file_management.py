"""File Management-related prism_tools command handlers.

Mirrors the Studio GUI's File Management page (app/src/web/blueprints/
tools.py's /api/file-management/* routes), which is otherwise entirely
GUI-only. See docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Callable

from src.bids_file_deleter import BidsFileDeleter
from src.physio_renamer import plan_rename
from src.project_manager import ProjectManager

parse_bids_filename: Callable[[str], dict[object, object] | None] | None
try:
    from src.batch_convert import parse_bids_filename
except ImportError:
    parse_bids_filename = None

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


def cmd_file_management_remove_scans_tsv(args) -> None:
    """Delete every `*_scans.tsv` file across a project (superdataset plus
    nested subject/derivatives subdatasets) — the CLI equivalent of the
    Studio GUI's File Management -> "Delete all scans.tsv" action
    (ProjectManager.remove_scans_tsv_files). This modifies the project in
    place and commits the removal, so it requires --yes just like the
    GUI's explicit confirmation requirement."""
    as_json = bool(getattr(args, "json", False))
    project_root = Path(args.project).resolve()

    if not getattr(args, "yes", False) and not as_json:
        confirmation = (
            input(
                f"Delete every *_scans.tsv file in {project_root}? This modifies the "
                "project in place and cannot be undone from the CLI. [y/N] "
            )
            .strip()
            .lower()
        )
        if confirmation not in {"y", "yes"}:
            print("Aborted.")
            return
    elif not getattr(args, "yes", False):
        if as_json:
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": "--yes is required with --json (no interactive confirmation available)",
                    },
                    indent=2,
                )
            )
        sys.exit(1)

    manager = ProjectManager()
    result = manager.remove_scans_tsv_files(project_root)

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        if not result.get("success"):
            print(f"Error: {result.get('message') or result.get('errors')}")
            sys.exit(1)
        print(
            f"Done: {result.get('removed', 0)} scans.tsv file(s) removed across "
            f"{len(result.get('dataset_roots_touched', []))} dataset root(s)."
        )
        if result.get("errors"):
            for error in result["errors"]:
                print(f"⚠ {error}")


def _scan_input_folder(input_root: Path) -> list[tuple[str, str]]:
    """List files under input_root as (absolute_path, relative_path) pairs,
    skipping dotfiles/dot-directories — matches the Studio GUI's server-side
    folder scan for the physio renamer's `folder_path` input."""
    entries: list[tuple[str, str]] = []
    for candidate in sorted(input_root.rglob("*")):
        if not candidate.is_file():
            continue
        if any(part.startswith(".") for part in candidate.parts):
            continue
        entries.append((str(candidate), candidate.relative_to(input_root).as_posix()))
    return entries


def cmd_file_management_rename_physio(args) -> None:
    """Preview or apply a regex-based batch rename of physio/eyetracking
    files — the CLI equivalent of the Studio GUI's File Management /
    Converter -> Physio Renamer action (src.physio_renamer.plan_rename)."""
    as_json = bool(getattr(args, "json", False))
    input_root = Path(args.input).resolve()
    if not input_root.is_dir():
        print(f"Error: --input is not a directory: {input_root}")
        sys.exit(1)

    entries = _scan_input_folder(input_root)
    if not entries:
        if as_json:
            print(json.dumps({"success": True, "applied": False, "results": []}, indent=2))
        else:
            print(f"No files found under {input_root}.")
        return

    try:
        results, warnings = plan_rename(
            entries,
            pattern=args.pattern,
            replacement=args.replacement,
            id_source=args.id_source,
            folder_subject_level=args.folder_subject_level,
            folder_session_level=args.folder_session_level,
            folder_example_path=args.folder_example_path or "",
            folder_subject_value=args.folder_subject_value or "",
            folder_session_value=args.folder_session_value or "",
            modality=args.modality,
            organize=bool(getattr(args, "organize", False)),
            parse_bids_filename=parse_bids_filename,
        )
    except ValueError as error:
        error_message = str(error)
        if as_json:
            print(json.dumps({"success": False, "error": error_message}, indent=2))
        else:
            print(f"Error: {error_message}")
        sys.exit(1)

    failed = [r for r in results if not r["success"]]

    if not getattr(args, "apply", False):
        if as_json:
            print(
                json.dumps(
                    {
                        "success": True,
                        "applied": False,
                        "results": results,
                        "warnings": warnings,
                    },
                    indent=2,
                )
            )
        else:
            print("Preview only — pass --apply and --output to write renamed files.")
            for entry in results:
                if entry["success"]:
                    print(f"  {entry['old']} -> {entry['path']}")
                else:
                    print(f"  {entry['old']}: ERROR: {entry['new']}")
            if failed:
                print(f"{len(failed)} file(s) could not be renamed.")
        return

    if not args.output:
        print("Error: --output is required with --apply")
        sys.exit(1)

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    copy_errors: list[str] = []
    for entry in results:
        if not entry["success"]:
            copy_errors.append(f"{entry['old']}: {entry['new']}")
            continue
        source = Path(entry["old"])
        dest = output_root / entry["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied += 1

    if as_json:
        print(
            json.dumps(
                {
                    "success": True,
                    "applied": True,
                    "copied": copied,
                    "errors": copy_errors,
                    "results": results,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
    else:
        print(f"Done: {copied} file(s) copied to {output_root}.")
        if copy_errors:
            print(f"{len(copy_errors)} file(s) failed:")
            for copy_error in copy_errors:
                print(f"  ✗ {copy_error}")
