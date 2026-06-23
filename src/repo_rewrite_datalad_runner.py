from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from src.bids_entity_parser import BidsEntityParser
from src.bids_entity_rewriter import BidsEntityRewriter
from src.datalad_execution import (
    is_datalad_dataset,
    resolve_datalad_executable,
    run_datalad_get_paths,
    run_datalad_save,
    run_datalad_unlock,
)
from src.subject_code_rewriter import SubjectCodeRewriter


def _fetch_all_content_before_rewrite(
    root: Path,
    *,
    subject_groups: list[str],
    rename_sources: list[str],
    text_update_sources: list[str],
    datalad_executable: str,
    add_log: Callable[[str, str], None],
) -> set[str]:
    """Fetch every subject's content *before* any subject's rename/save
    begins, instead of discovering one at a time (mid-batch) that some
    subject's data was never actually downloaded. Returns the set of subject
    groups whose content could not be fetched from any known remote, so the
    caller can skip them up front rather than leaving a partially-renamed
    dataset behind.

    Checked one subject group at a time (mirroring the main loop's own
    per-group get) rather than batched into one big `datalad get` call, so
    one subject's unfetchable content can never cause an unrelated subject
    to be skipped.
    """
    unavailable_subjects: set[str] = set()

    for subject_group in subject_groups:
        group_get_paths = [
            path_text
            for path_text in rename_sources
            if subject_group == "dataset-root"
            or _extract_subject_from_path(path_text) == subject_group
        ]
        group_content_paths = [
            path_text
            for path_text in text_update_sources
            if subject_group == "dataset-root"
            or _extract_subject_from_path(path_text) == subject_group
        ]

        for paths, recursive, no_data in (
            (group_get_paths, True, True),
            (group_content_paths, False, False),
        ):
            if not paths:
                continue
            result = run_datalad_get_paths(
                root,
                paths=paths,
                datalad_executable=datalad_executable,
                recursive=recursive,
                no_data=no_data,
            )
            if not result.get("success"):
                unavailable_subjects.add(subject_group)
                add_log(
                    f"[{subject_group}] Pre-flight fetch failed; this subject "
                    f"will be skipped: {result.get('message') or 'Unknown DataLad error.'}",
                    "warning",
                )
                break

    if unavailable_subjects:
        add_log(
            f"{len(unavailable_subjects)} subject group(s) will be skipped "
            "because their content is not available from any known remote "
            f"(not even the original source): {', '.join(sorted(unavailable_subjects))}.",
            "error",
        )

    return unavailable_subjects


class TrackedRewriteError(ValueError):
    """Raised when a DataLad-tracked rewrite mutation fails partway through.

    Carries the log entries accumulated before the failure so the UI can show
    exactly which subject group and step (get/unlock/save) failed.
    """

    def __init__(self, message: str, log: list[dict[str, str]]):
        super().__init__(message)
        self.log = log


class RewriteCancelledError(RuntimeError):
    """Raised when a caller-supplied is_cancelled() callback returns True
    between subject groups, so a long batch can be aborted cleanly between
    DataLad commits rather than only at the very end."""


def _extract_subject_from_path(path_text: str) -> str | None:
    return BidsEntityParser.extract_subject_from_path(path_text)


def _apply_mutation_locally_with_datalad_save(
    *,
    project_root: Path,
    run_message: str,
    get_paths: list[str],
    content_paths: list[str],
    apply_fn: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a mutation directly in-process, backed by DataLad get/unlock
    beforehand and a plain `datalad save` afterward.

    This deliberately avoids `datalad run`: its clean-working-tree
    precondition (which an unlock step itself can violate) and its
    `{placeholder}`-style command templating (which collides with literal
    curly braces in any embedded Python dict/set literal) turned out to be
    repeated, hard-to-diagnose failure points on real multi-subject
    datasets. `datalad save` has neither constraint — it just commits
    whatever the in-process mutation actually changed.
    """
    root = Path(project_root)
    if not is_datalad_dataset(root):
        return apply_fn(), {"tracked": False, "used_run": False}

    datalad_executable = resolve_datalad_executable()
    if not datalad_executable:
        raise ValueError(
            "This project is tracked by DataLad and mutation changes require "
            "DataLad. Install with: uv tool install datalad git-annex."
        )

    autosave_result = run_datalad_save(
        root,
        message=f'PRISM: autosave pending changes before "{run_message}"',
        datalad_executable=datalad_executable,
    )
    if not autosave_result.get("success"):
        raise ValueError(
            str(
                autosave_result.get("message")
                or "DataLad autosave failed before mutation."
            )
        )

    get_result: dict[str, Any] = {"attempted": False, "success": True, "message": "", "command": ""}
    if get_paths:
        get_result = run_datalad_get_paths(
            root,
            paths=get_paths,
            datalad_executable=datalad_executable,
            recursive=True,
            no_data=True,
        )
        if not get_result.get("success"):
            raise ValueError(
                str(get_result.get("message") or "DataLad get failed before mutation.")
            )

    # `content_paths` are files the mutation will read+rewrite in place
    # (e.g. updating subject IDs inside a .tsv/.json). Those need full
    # content present locally (not just `-n` presence) and need to be
    # unlocked, since annexed files are normally read-only symlinks.
    content_get_result: dict[str, Any] = {"attempted": False, "success": True, "message": "", "command": ""}
    unlock_result: dict[str, Any] = {"attempted": False, "success": True, "message": "", "command": ""}
    if content_paths:
        content_get_result = run_datalad_get_paths(
            root,
            paths=content_paths,
            datalad_executable=datalad_executable,
            recursive=False,
            no_data=False,
        )
        if not content_get_result.get("success"):
            raise ValueError(
                str(
                    content_get_result.get("message")
                    or "DataLad get (content) failed before mutation."
                )
            )

        unlock_result = run_datalad_unlock(
            root,
            paths=content_paths,
            datalad_executable=datalad_executable,
        )

        # `datalad unlock` is treated as best-effort (it's a harmless no-op
        # for files that aren't annexed), so its own exit code can't be
        # trusted to tell us whether the file actually became writable.
        # Check the real, ground-truth condition instead of trusting the
        # tool's report.
        still_locked = [
            path_text
            for path_text in content_paths
            if (root / path_text).exists() and not os.access(root / path_text, os.W_OK)
        ]
        if still_locked:
            raise ValueError(
                "These files are still read-only after 'datalad unlock' and "
                "the mutation would fail trying to write to them: "
                f"{', '.join(still_locked)}. DataLad unlock said: "
                f"{unlock_result.get('message') or '(no message)'}"
            )

    payload = apply_fn()

    save_result = run_datalad_save(
        root,
        message=run_message,
        datalad_executable=datalad_executable,
        recursive=True,
    )
    if not save_result.get("success"):
        raise ValueError(
            str(save_result.get("message") or "DataLad save failed after mutation.")
        )

    mutation_result = {
        "tracked": True,
        "used_run": False,
        "executable": datalad_executable,
        "autosave": autosave_result,
        "get": get_result,
        "content_get": content_get_result,
        "unlock": unlock_result,
        "save": save_result,
    }
    return payload, mutation_result


def apply_subject_rewrite(
    project_root: Path,
    *,
    mode: str,
    example_subject: str | None,
    keep_fragment: str | None,
    allow_many_to_one: bool,
    on_log: Callable[[str, str], None] | None = None,
    on_subject_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    rewriter = SubjectCodeRewriter(root)
    log: list[dict[str, str]] = []

    def add_log(message: str, level: str = "info") -> None:
        log.append({"message": message, "level": level})
        if on_log is not None:
            try:
                on_log(message, level)
            except Exception:
                pass

    # cap_results=False: this preview drives internal orchestration (which
    # files get a DataLad get/unlock before each subject's mutation), not a
    # UI display, so it must see the complete lists rather than the first 200.
    preview = rewriter.preview(
        mode=mode,
        example_subject=example_subject,
        keep_fragment=keep_fragment,
        allow_many_to_one=allow_many_to_one,
        cap_results=False,
    )

    should_use_datalad = (
        is_datalad_dataset(root)
        and (
            int(preview.get("file_rename_count") or 0) > 0
            or int(preview.get("directory_rename_count") or 0) > 0
        )
    )
    if not should_use_datalad:
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
    # verbatim for every subject group's mutation — re-deriving the mapping
    # from example_subject/keep_fragment after an earlier subject in the
    # same batch has already been renamed would fail because the example
    # subject no longer exists under its old name.
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
        "Project is tracked by DataLad; each group will be applied and "
        "saved as its own DataLad commit.",
        "step",
    )

    failed_groups: list[dict[str, str]] = []
    datalad_executable = resolve_datalad_executable()
    if datalad_executable:
        add_log(
            "Verifying all affected content is actually downloaded before "
            "renaming anything...",
            "step",
        )
        unavailable_subjects = _fetch_all_content_before_rewrite(
            root,
            subject_groups=subject_groups,
            rename_sources=rename_sources,
            text_update_sources=text_update_sources,
            datalad_executable=datalad_executable,
            add_log=add_log,
        )
        if unavailable_subjects:
            subject_groups = [
                subject for subject in subject_groups if subject not in unavailable_subjects
            ]
            for subject in sorted(unavailable_subjects):
                failed_groups.append({
                    "subject": subject,
                    "error": (
                        "Content is not available from any known remote; "
                        "skipped before any rename was attempted."
                    ),
                })

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

    total_subject_groups = len(subject_groups)
    for group_index, subject_group in enumerate(subject_groups):
        if is_cancelled is not None and is_cancelled():
            add_log(
                f"Cancelled by user after {group_index} of {total_subject_groups} "
                "subject group(s).",
                "warning",
            )
            raise RewriteCancelledError(
                f"Cancelled after {group_index} of {total_subject_groups} subject group(s)."
            )

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
        add_log(
            f"[{subject_group}] Fetching content, unlocking annexed text "
            "files, applying rename, and saving via DataLad...",
            "step",
        )
        try:
            payload, mutation_result = _apply_mutation_locally_with_datalad_save(
                project_root=root,
                run_message=run_message,
                get_paths=get_paths,
                content_paths=content_paths,
                apply_fn=lambda: rewriter.apply(
                    mode=mode,
                    allow_many_to_one=allow_many_to_one,
                    subjects=subjects_arg,
                    explicit_mapping=explicit_mapping_for_group,
                ),
            )
        except Exception as exc:
            # Don't abort the whole batch on one bad subject group (e.g. a
            # real-world dataset with inconsistently-nested DataLad
            # subdatasets where one subject's presence check fails for
            # reasons unrelated to the rename itself). Each group is its
            # own atomic get/unlock/apply/save cycle, so subjects already
            # renamed stay renamed; record this one as failed and keep
            # going so the rest of the batch isn't held hostage by it.
            add_log(f"[{subject_group}] {exc}", "error")
            failed_groups.append({"subject": subject_group, "error": str(exc)})
            continue

        for step_name in ("autosave", "get", "content_get", "unlock", "save"):
            step_info = (
                mutation_result.get(step_name)
                if isinstance(mutation_result, dict)
                else None
            )
            if isinstance(step_info, dict) and step_info.get("message"):
                add_log(f"[{subject_group}] {step_info['message']}", "info")

        if on_subject_progress is not None:
            try:
                on_subject_progress(group_index + 1, total_subject_groups)
            except Exception:
                pass

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
                "save": mutation_result.get("save") if isinstance(mutation_result, dict) else None,
            }
        )

    if failed_groups:
        succeeded_subjects = ", ".join(d["subject"] for d in group_details) or "(none)"
        failed_text = "; ".join(
            f"{d['subject']} ({d['error']})" for d in failed_groups
        )
        add_log(
            f"Rename partially completed: {len(group_details)} of "
            f"{total_subject_groups} subject group(s) succeeded "
            f"({succeeded_subjects}); {len(failed_groups)} failed: {failed_text}",
            "error",
        )
        raise TrackedRewriteError(
            f"{len(group_details)} of {total_subject_groups} subject "
            f"group(s) were renamed successfully and saved; "
            f"{len(failed_groups)} failed and were left unchanged: "
            f"{failed_text}",
            log,
        )

    add_log(
        f"Rename complete: {total_mapping} subject mapping(s), "
        f"{total_directory_renames} folder rename(s), {total_file_renames} "
        f"filename rename(s) across {len(group_details)} DataLad save(s).",
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
            "used_run": False,
            "tracked": True,
            "save_per_subject": True,
            "save_count": len(group_details),
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
    on_log: Callable[[str, str], None] | None = None,
    on_subject_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    rewriter = BidsEntityRewriter(root)
    log: list[dict[str, str]] = []

    def add_log(message: str, level: str = "info") -> None:
        log.append({"message": message, "level": level})
        if on_log is not None:
            try:
                on_log(message, level)
            except Exception:
                pass

    # cap_results=False: this preview drives internal orchestration (which
    # files get a DataLad get/unlock before each subject's mutation), not a
    # UI display, so it must see the complete lists rather than the first 200.
    preview = rewriter.preview(
        modality=modality,
        entity=entity,
        current_value=current_value,
        operation=operation,
        replacement=replacement,
        cap_results=False,
    )

    should_use_datalad = (
        is_datalad_dataset(root)
        and int(preview.get("rename_count") or 0) > 0
    )
    if not should_use_datalad:
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
    # Resolved once, against the dataset's pre-rename state, and reused
    # verbatim for every subject group's mutation — re-deriving file renames
    # from modality/entity/current_value after an earlier subject in the
    # same batch has already been renamed could change the set of distinct
    # values left for this entity (e.g. ambiguity errors, or the requested
    # current_value no longer existing).
    full_renames = [
        {"from": str(item.get("from") or ""), "to": str(item.get("to") or "")}
        for item in list(preview.get("renames") or [])
        if isinstance(item, dict) and item.get("from") and item.get("to")
    ]
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
        "Project is tracked by DataLad; each group will be applied and "
        "saved as its own DataLad commit.",
        "step",
    )

    failed_groups: list[dict[str, str]] = []
    datalad_executable = resolve_datalad_executable()
    if datalad_executable:
        add_log(
            "Verifying all affected content is actually downloaded before "
            "renaming anything...",
            "step",
        )
        unavailable_subjects = _fetch_all_content_before_rewrite(
            root,
            subject_groups=subject_groups,
            rename_sources=rename_sources,
            text_update_sources=text_update_sources,
            datalad_executable=datalad_executable,
            add_log=add_log,
        )
        if unavailable_subjects:
            subject_groups = [
                subject for subject in subject_groups if subject not in unavailable_subjects
            ]
            for subject in sorted(unavailable_subjects):
                failed_groups.append({
                    "subject": subject,
                    "error": (
                        "Content is not available from any known remote; "
                        "skipped before any rename was attempted."
                    ),
                })

    aggregate_renames: list[dict[str, str]] = []
    aggregate_text_update_files: list[str] = []
    aggregate_conflicts: list[str] = []
    group_details: list[dict[str, Any]] = []
    rename_seen: set[tuple[str, str]] = set()
    text_update_seen: set[str] = set()
    conflict_seen: set[str] = set()
    total_rename_count = 0

    total_subject_groups = len(subject_groups)
    for group_index, subject_group in enumerate(subject_groups):
        if is_cancelled is not None and is_cancelled():
            add_log(
                f"Cancelled by user after {group_index} of {total_subject_groups} "
                "subject group(s).",
                "warning",
            )
            raise RewriteCancelledError(
                f"Cancelled after {group_index} of {total_subject_groups} subject group(s)."
            )

        subjects_arg = None if subject_group == "dataset-root" else [subject_group]
        explicit_renames_for_group = [
            item
            for item in full_renames
            if subject_group == "dataset-root"
            or _extract_subject_from_path(item["from"]) == subject_group
        ]

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
        add_log(
            f"[{subject_group}] Fetching content, unlocking annexed text "
            "files, applying rename, and saving via DataLad...",
            "step",
        )
        try:
            payload, mutation_result = _apply_mutation_locally_with_datalad_save(
                project_root=root,
                run_message=run_message,
                get_paths=get_paths,
                content_paths=content_paths,
                apply_fn=lambda: rewriter.apply(
                    modality=modality,
                    entity=entity,
                    current_value=current_value,
                    operation=operation,
                    replacement=replacement,
                    subjects=subjects_arg,
                    explicit_renames=explicit_renames_for_group,
                ),
            )
        except Exception as exc:
            # Same reasoning as apply_subject_rewrite: don't abort the whole
            # batch on one subject group's failure (e.g. an inconsistently
            # nested DataLad subdataset). Record it and keep going so the
            # rest of the batch isn't held hostage by an unrelated subject.
            add_log(f"[{subject_group}] {exc}", "error")
            failed_groups.append({"subject": subject_group, "error": str(exc)})
            continue

        for step_name in ("autosave", "get", "content_get", "unlock", "save"):
            step_info = (
                mutation_result.get(step_name)
                if isinstance(mutation_result, dict)
                else None
            )
            if isinstance(step_info, dict) and step_info.get("message"):
                add_log(f"[{subject_group}] {step_info['message']}", "info")

        if on_subject_progress is not None:
            try:
                on_subject_progress(group_index + 1, total_subject_groups)
            except Exception:
                pass

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
                "save": mutation_result.get("save") if isinstance(mutation_result, dict) else None,
            }
        )

    if failed_groups:
        succeeded_subjects = ", ".join(d["subject"] for d in group_details) or "(none)"
        failed_text = "; ".join(
            f"{d['subject']} ({d['error']})" for d in failed_groups
        )
        add_log(
            f"Rename partially completed: {len(group_details)} of "
            f"{total_subject_groups} subject group(s) succeeded "
            f"({succeeded_subjects}); {len(failed_groups)} failed: {failed_text}",
            "error",
        )
        raise TrackedRewriteError(
            f"{len(group_details)} of {total_subject_groups} subject "
            f"group(s) were renamed successfully and saved; "
            f"{len(failed_groups)} failed and were left unchanged: "
            f"{failed_text}",
            log,
        )

    add_log(
        f"Rename complete: {total_rename_count} filename rename(s) across "
        f"{len(group_details)} DataLad save(s).",
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
            "used_run": False,
            "tracked": True,
            "save_per_subject": True,
            "save_count": len(group_details),
            "groups": group_details,
        },
    }
