from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from src.bids_entity_rewriter import BidsEntityRewriter
from src.datalad_execution import (
    is_datalad_dataset,
    parse_json_from_output,
)
from src.datalad_mutation_policy import build_pythonpath_env, run_tracked_mutation
from src.subject_code_rewriter import SubjectCodeRewriter

_SUBJECT_DIR_PATTERN = re.compile(r"^sub-[A-Za-z0-9]+$")


def _extract_subject_from_path(path_text: str) -> str | None:
    for part in Path(str(path_text or "").strip()).parts:
        if _SUBJECT_DIR_PATTERN.fullmatch(part):
            return part
    return None


def _run_wrapped_command_with_mutation_or_raise(
    *,
    project_root: Path,
    message: str,
    command: list[str],
    get_paths: list[str],
    get_recursive: bool,
    get_no_data: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mutation_result = run_tracked_mutation(
        project_root,
        get_paths=get_paths,
        run_message=message,
        command=command,
        get_timeout_seconds=1800,
        run_timeout_seconds=3600,
        get_recursive=get_recursive,
        get_no_data=get_no_data,
        env=build_pythonpath_env(),
    )

    run_info = mutation_result.get("run") if isinstance(mutation_result, dict) else {}
    payload = parse_json_from_output(str((run_info or {}).get("stdout") or ""))
    if not isinstance(payload, dict):
        raise ValueError(
            "DataLad run finished, but PRISM could not parse rewrite output."
        )

    if not isinstance(mutation_result, dict):
        mutation_result = {}

    return payload, mutation_result


def apply_subject_rewrite(
    project_root: Path,
    *,
    mode: str,
    example_subject: str | None,
    keep_fragment: str | None,
    allow_many_to_one: bool,
) -> dict[str, Any]:
    root = Path(project_root)
    rewriter = SubjectCodeRewriter(root)

    preview = rewriter.preview(
        mode=mode,
        example_subject=example_subject,
        keep_fragment=keep_fragment,
        allow_many_to_one=allow_many_to_one,
    )

    should_use_datalad_run = (
        is_datalad_dataset(root)
        and (
            int(preview.get("file_rename_count") or 0) > 0
            or int(preview.get("directory_rename_count") or 0) > 0
        )
    )
    if not should_use_datalad_run:
        return rewriter.apply(
            mode=mode,
            example_subject=example_subject,
            keep_fragment=keep_fragment,
            allow_many_to_one=allow_many_to_one,
        )

    rename_sources = sorted(
        {
            str(item.get("from") or "").strip()
            for item in list(preview.get("file_renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
        | {
            str(item.get("from") or "").strip()
            for item in list(preview.get("directory_renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
    )
    subject_groups = sorted(
        {
            subject
            for subject in (
                _extract_subject_from_path(path_text)
                for path_text in rename_sources
            )
            if subject
        }
    )
    if not subject_groups:
        subject_groups = sorted(
            {
                str(key)
                for key in dict(preview.get("mapping") or {}).keys()
                if _SUBJECT_DIR_PATTERN.fullmatch(str(key))
            }
        )
    if not subject_groups:
        subject_groups = ["dataset-root"]

    aggregate_mapping: dict[str, str] = {}
    aggregate_file_renames: list[dict[str, str]] = []
    aggregate_directory_renames: list[dict[str, str]] = []
    aggregate_text_update_files: list[str] = []
    aggregate_conflicts: list[str] = []
    group_details: list[dict[str, Any]] = []
    file_rename_seen: set[tuple[str, str]] = set()
    directory_rename_seen: set[tuple[str, str]] = set()
    text_update_seen: set[str] = set()
    conflict_seen: set[str] = set()
    total_mapping = 0
    total_file_renames = 0
    total_directory_renames = 0

    for subject_group in subject_groups:
        subjects_arg = None if subject_group == "dataset-root" else [subject_group]
        script = (
            "import json;"
            "from pathlib import Path;"
            "from src.subject_code_rewriter import SubjectCodeRewriter;"
            f"result=SubjectCodeRewriter(Path({json.dumps(str(root))})).apply("
            f"mode={json.dumps(mode)},"
            f"example_subject={json.dumps(example_subject)},"
            f"keep_fragment={json.dumps(keep_fragment)},"
            f"allow_many_to_one={json.dumps(bool(allow_many_to_one))},"
            f"subjects={json.dumps(subjects_arg)}"
            ");"
            "print(json.dumps(result, ensure_ascii=False))"
        )

        get_paths = sorted(
            {
                path_text
                for path_text in rename_sources
                if subject_group == "dataset-root"
                or _extract_subject_from_path(path_text) == subject_group
            }
        )
        if not get_paths:
            get_paths = ["."]

        run_message = (
            f"PRISM: Rewrite subject IDs ({subject_group})"
            if subject_group != "dataset-root"
            else "PRISM: Rewrite subject IDs"
        )
        payload, mutation_result = _run_wrapped_command_with_mutation_or_raise(
            project_root=root,
            message=run_message,
            command=[sys.executable, "-c", script],
            get_paths=get_paths,
            get_recursive=True,
            get_no_data=True,
        )

        total_mapping += int(payload.get("mapping_count") or 0)
        total_file_renames += int(payload.get("file_rename_count") or 0)
        total_directory_renames += int(payload.get("directory_rename_count") or 0)
        aggregate_mapping.update(dict(payload.get("mapping") or {}))

        for rename in list(payload.get("file_renames") or []):
            if not isinstance(rename, dict):
                continue
            from_path = str(rename.get("from") or "")
            to_path = str(rename.get("to") or "")
            key = (from_path, to_path)
            if key in file_rename_seen:
                continue
            file_rename_seen.add(key)
            aggregate_file_renames.append({"from": from_path, "to": to_path})

        for rename in list(payload.get("directory_renames") or []):
            if not isinstance(rename, dict):
                continue
            from_path = str(rename.get("from") or "")
            to_path = str(rename.get("to") or "")
            key = (from_path, to_path)
            if key in directory_rename_seen:
                continue
            directory_rename_seen.add(key)
            aggregate_directory_renames.append({"from": from_path, "to": to_path})

        for text_file in list(payload.get("text_update_files") or []):
            normalized = str(text_file)
            if normalized in text_update_seen:
                continue
            text_update_seen.add(normalized)
            aggregate_text_update_files.append(normalized)

        for conflict in list(payload.get("conflicts") or []):
            normalized = str(conflict)
            if normalized in conflict_seen:
                continue
            conflict_seen.add(normalized)
            aggregate_conflicts.append(normalized)

        group_details.append(
            {
                "subject": subject_group,
                "get": mutation_result.get("get") if isinstance(mutation_result, dict) else None,
                "run": mutation_result.get("run") if isinstance(mutation_result, dict) else None,
            }
        )

    return {
        "mode": preview.get("mode") or mode,
        "rule": preview.get("rule"),
        "allow_many_to_one": bool(preview.get("allow_many_to_one") or allow_many_to_one),
        "subjects": [s for s in subject_groups if s != "dataset-root"],
        "applied": True,
        "subject_examples": list(preview.get("subject_examples") or [])[:200],
        "subject_token_sources": dict(preview.get("subject_token_sources") or {}),
        "mapping": dict(sorted(aggregate_mapping.items())),
        "mapping_count": total_mapping,
        "directory_rename_count": total_directory_renames,
        "file_rename_count": total_file_renames,
        "text_update_count": len(aggregate_text_update_files),
        "directory_renames": aggregate_directory_renames[:200],
        "file_renames": aggregate_file_renames[:200],
        "text_update_files": aggregate_text_update_files[:200],
        "conflicts": aggregate_conflicts,
        "datalad": {
            "used_run": True,
            "tracked": True,
            "run_per_subject": True,
            "run_count": len(group_details),
            "groups": group_details,
        },
    }


def apply_entity_rewrite(
    project_root: Path,
    *,
    modality: str,
    entity: str,
    operation: str,
    current_value: str | None,
    replacement: str | None,
) -> dict[str, Any]:
    root = Path(project_root)
    rewriter = BidsEntityRewriter(root)

    preview = rewriter.preview(
        modality=modality,
        entity=entity,
        current_value=current_value,
        operation=operation,
        replacement=replacement,
    )

    should_use_datalad_run = (
        is_datalad_dataset(root)
        and int(preview.get("rename_count") or 0) > 0
    )
    if not should_use_datalad_run:
        return rewriter.apply(
            modality=modality,
            entity=entity,
            current_value=current_value,
            operation=operation,
            replacement=replacement,
        )

    rename_sources = sorted(
        {
            str(item.get("from") or "").strip()
            for item in list(preview.get("renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
    )
    subject_groups = sorted(
        {
            subject
            for subject in (
                _extract_subject_from_path(path_text)
                for path_text in rename_sources
            )
            if subject
        }
    )
    if not subject_groups:
        subject_groups = ["dataset-root"]

    aggregate_renames: list[dict[str, str]] = []
    aggregate_text_update_files: list[str] = []
    aggregate_conflicts: list[str] = []
    group_details: list[dict[str, Any]] = []
    rename_seen: set[tuple[str, str]] = set()
    text_update_seen: set[str] = set()
    conflict_seen: set[str] = set()
    total_rename_count = 0

    for subject_group in subject_groups:
        subjects_arg = None if subject_group == "dataset-root" else [subject_group]
        script = (
            "import json;"
            "from pathlib import Path;"
            "from src.bids_entity_rewriter import BidsEntityRewriter;"
            f"result=BidsEntityRewriter(Path({json.dumps(str(root))})).apply("
            f"modality={json.dumps(modality)},"
            f"entity={json.dumps(entity)},"
            f"operation={json.dumps(operation)},"
            f"current_value={json.dumps(current_value)},"
            f"replacement={json.dumps(replacement)},"
            f"subjects={json.dumps(subjects_arg)}"
            ");"
            "print(json.dumps(result, ensure_ascii=False))"
        )

        get_paths = sorted(
            {
                path_text
                for path_text in rename_sources
                if subject_group == "dataset-root"
                or _extract_subject_from_path(path_text) == subject_group
            }
        )
        if not get_paths:
            get_paths = ["."]

        run_message = (
            f"PRISM: Rewrite BIDS filename entity ({subject_group})"
            if subject_group != "dataset-root"
            else "PRISM: Rewrite BIDS filename entity"
        )
        payload, mutation_result = _run_wrapped_command_with_mutation_or_raise(
            project_root=root,
            message=run_message,
            command=[sys.executable, "-c", script],
            get_paths=get_paths,
            get_recursive=False,
            get_no_data=True,
        )

        total_rename_count += int(payload.get("rename_count") or 0)

        for rename in list(payload.get("renames") or []):
            if not isinstance(rename, dict):
                continue
            from_path = str(rename.get("from") or "")
            to_path = str(rename.get("to") or "")
            key = (from_path, to_path)
            if key in rename_seen:
                continue
            rename_seen.add(key)
            aggregate_renames.append({"from": from_path, "to": to_path})

        for text_file in list(payload.get("text_update_files") or []):
            normalized = str(text_file)
            if normalized in text_update_seen:
                continue
            text_update_seen.add(normalized)
            aggregate_text_update_files.append(normalized)

        for conflict in list(payload.get("conflicts") or []):
            normalized = str(conflict)
            if normalized in conflict_seen:
                continue
            conflict_seen.add(normalized)
            aggregate_conflicts.append(normalized)

        group_details.append(
            {
                "subject": subject_group,
                "get": mutation_result.get("get") if isinstance(mutation_result, dict) else None,
                "run": mutation_result.get("run") if isinstance(mutation_result, dict) else None,
            }
        )

    return {
        "modality": preview.get("modality") or modality,
        "entity": preview.get("entity") or entity,
        "current_value": preview.get("current_value") or (current_value or ""),
        "operation": preview.get("operation") or operation,
        "replacement": preview.get("replacement") or (replacement or ""),
        "available_modalities": list(preview.get("available_modalities") or []),
        "available_entities": list(preview.get("available_entities") or []),
        "subjects": [s for s in subject_groups if s != "dataset-root"],
        "applied": True,
        "rename_count": total_rename_count,
        "text_update_count": len(aggregate_text_update_files),
        "renames": aggregate_renames[:200],
        "text_update_files": aggregate_text_update_files[:200],
        "conflicts": aggregate_conflicts,
        "datalad": {
            "used_run": True,
            "tracked": True,
            "run_per_subject": True,
            "run_count": len(group_details),
            "groups": group_details,
        },
    }
