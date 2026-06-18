from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.bids_entity_parser import BidsEntityParser
from src.bids_entity_rewriter import BidsEntityRewriter
from src.datalad_execution import (
    is_datalad_dataset,
    parse_json_from_output,
)
from src.datalad_mutation_policy import build_pythonpath_env, run_tracked_mutation
from src.subject_code_rewriter import SubjectCodeRewriter


class TrackedRewriteError(ValueError):
    """Raised when a DataLad-tracked rewrite mutation fails partway through.

    Carries the log entries accumulated before the failure so the UI can show
    exactly which subject group and step (autosave/get/run) failed.
    """

    def __init__(self, message: str, log: list[dict[str, str]]):
        super().__init__(message)
        self.log = log


def _extract_subject_from_path(path_text: str) -> str | None:
    return BidsEntityParser.extract_subject_from_path(path_text)


def _run_wrapped_command_with_mutation_or_raise(
    *,
    project_root: Path,
    message: str,
    command: list[str],
    get_paths: list[str],
    get_recursive: bool,
    get_no_data: bool,
    content_paths: list[str] | None = None,
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
        content_paths=content_paths or [],
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
    log: list[dict[str, str]] = []

    def add_log(message: str, level: str = "info") -> None:
        log.append({"message": message, "level": level})

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
        result = rewriter.apply(
            mode=mode,
            example_subject=example_subject,
            keep_fragment=keep_fragment,
            allow_many_to_one=allow_many_to_one,
        )
        if isinstance(result, dict):
            add_log(
                "Project is not tracked by DataLad (or no renames were needed); "
                "applied directly.",
                "info",
            )
            result.setdefault("log", log)
        return result

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
    text_update_sources = sorted(
        {
            str(path_text).strip()
            for path_text in list(preview.get("text_update_files") or [])
            if str(path_text or "").strip()
        }
    )
    # Resolved once, against the dataset's pre-rename state, and reused
    # verbatim by every subject group's subprocess (see explicit_mapping
    # below) — re-deriving the mapping from example_subject/keep_fragment
    # inside each subprocess would fail once an earlier subject in the same
    # batch has already been renamed and the example no longer exists.
    full_mapping = dict(preview.get("mapping") or {})
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
                for key in full_mapping.keys()
                if BidsEntityParser.is_subject_dir(str(key))
            }
        )
    if not subject_groups:
        subject_groups = ["dataset-root"]

    add_log(
        f"Found {len(subject_groups)} subject group(s) requiring rename. "
        "Project is tracked by DataLad; each group will run as its own "
        "tracked DataLad run.",
        "step",
    )

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
        explicit_mapping_for_group = (
            full_mapping
            if subject_group == "dataset-root"
            else (
                {subject_group: full_mapping[subject_group]}
                if subject_group in full_mapping
                else {}
            )
        )
        # Use repr() (not json.dumps()) to embed these as Python source literals —
        # json.dumps() emits JSON syntax (true/false/null) which is not valid
        # Python (True/False/None) and breaks the subprocess with a NameError.
        script = (
            "import json;"
            "from pathlib import Path;"
            "from src.subject_code_rewriter import SubjectCodeRewriter;"
            f"result=SubjectCodeRewriter(Path({str(root)!r})).apply("
            f"mode={mode!r},"
            f"allow_many_to_one={bool(allow_many_to_one)!r},"
            f"subjects={subjects_arg!r},"
            f"explicit_mapping={explicit_mapping_for_group!r}"
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

        content_paths = sorted(
            {
                path_text
                for path_text in text_update_sources
                if subject_group == "dataset-root"
                or _extract_subject_from_path(path_text) == subject_group
            }
        )

        run_message = (
            f"PRISM: Rewrite subject IDs ({subject_group})"
            if subject_group != "dataset-root"
            else "PRISM: Rewrite subject IDs"
        )
        add_log(f"[{subject_group}] Autosaving pending changes, fetching content, "
                f"unlocking annexed text files, and applying rename via DataLad run...", "step")
        try:
            payload, mutation_result = _run_wrapped_command_with_mutation_or_raise(
                project_root=root,
                message=run_message,
                command=[sys.executable, "-c", script],
                get_paths=get_paths,
                get_recursive=True,
                get_no_data=True,
                content_paths=content_paths,
            )
        except ValueError as exc:
            add_log(f"[{subject_group}] {exc}", "error")
            raise TrackedRewriteError(str(exc), log) from exc

        for step_name in ("autosave", "get", "content_get", "unlock", "pre_run_autosave", "run"):
            step_info = (
                mutation_result.get(step_name)
                if isinstance(mutation_result, dict)
                else None
            )
            if isinstance(step_info, dict) and step_info.get("message"):
                add_log(f"[{subject_group}] {step_info['message']}", "info")

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

    add_log(
        f"Rename complete: {total_mapping} subject mapping(s), "
        f"{total_directory_renames} folder rename(s), {total_file_renames} "
        f"filename rename(s) across {len(group_details)} DataLad run(s).",
        "success",
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
        "log": log,
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
    log: list[dict[str, str]] = []

    def add_log(message: str, level: str = "info") -> None:
        log.append({"message": message, "level": level})

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
        result = rewriter.apply(
            modality=modality,
            entity=entity,
            current_value=current_value,
            operation=operation,
            replacement=replacement,
        )
        if isinstance(result, dict):
            add_log(
                "Project is not tracked by DataLad (or no renames were needed); "
                "applied directly.",
                "info",
            )
            result.setdefault("log", log)
        return result

    rename_sources = sorted(
        {
            str(item.get("from") or "").strip()
            for item in list(preview.get("renames") or [])
            if isinstance(item, dict) and str(item.get("from") or "").strip()
        }
    )
    text_update_sources = sorted(
        {
            str(path_text).strip()
            for path_text in list(preview.get("text_update_files") or [])
            if str(path_text or "").strip()
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

    add_log(
        f"Found {len(subject_groups)} subject group(s) requiring rename. "
        "Project is tracked by DataLad; each group will run as its own "
        "tracked DataLad run.",
        "step",
    )

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
        # Use repr() (not json.dumps()) to embed these as Python source literals —
        # json.dumps() emits JSON syntax (true/false/null) which is not valid
        # Python (True/False/None) and breaks the subprocess with a NameError.
        script = (
            "import json;"
            "from pathlib import Path;"
            "from src.bids_entity_rewriter import BidsEntityRewriter;"
            f"result=BidsEntityRewriter(Path({str(root)!r})).apply("
            f"modality={modality!r},"
            f"entity={entity!r},"
            f"operation={operation!r},"
            f"current_value={current_value!r},"
            f"replacement={replacement!r},"
            f"subjects={subjects_arg!r}"
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

        content_paths = sorted(
            {
                path_text
                for path_text in text_update_sources
                if subject_group == "dataset-root"
                or _extract_subject_from_path(path_text) == subject_group
            }
        )

        run_message = (
            f"PRISM: Rewrite BIDS filename entity ({subject_group})"
            if subject_group != "dataset-root"
            else "PRISM: Rewrite BIDS filename entity"
        )
        add_log(f"[{subject_group}] Autosaving pending changes, fetching content, "
                f"unlocking annexed text files, and applying rename via DataLad run...", "step")
        try:
            payload, mutation_result = _run_wrapped_command_with_mutation_or_raise(
                project_root=root,
                message=run_message,
                command=[sys.executable, "-c", script],
                get_paths=get_paths,
                get_recursive=False,
                get_no_data=True,
                content_paths=content_paths,
            )
        except ValueError as exc:
            add_log(f"[{subject_group}] {exc}", "error")
            raise TrackedRewriteError(str(exc), log) from exc

        for step_name in ("autosave", "get", "content_get", "unlock", "pre_run_autosave", "run"):
            step_info = (
                mutation_result.get(step_name)
                if isinstance(mutation_result, dict)
                else None
            )
            if isinstance(step_info, dict) and step_info.get("message"):
                add_log(f"[{subject_group}] {step_info['message']}", "info")

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

    add_log(
        f"Rename complete: {total_rename_count} filename rename(s) across "
        f"{len(group_details)} DataLad run(s).",
        "success",
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
        "log": log,
        "datalad": {
            "used_run": True,
            "tracked": True,
            "run_per_subject": True,
            "run_count": len(group_details),
            "groups": group_details,
        },
    }
