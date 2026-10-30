"""What happens after a conversion, once the converted files exist: save them into the project.

One function for ``survey convert`` and for Studio's Save to project: copy the files in (DataLad-aware, with a
commit), archive the source file, register the template versions in ``project.json``, clean up stale leftovers
and sync the recipe offsets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.datalad_project_copy import copy_files_into_project
from src.physio_renamer import (
    resolve_project_copy_root,
    rewrite_subject_in_relative_path,
    should_use_flat_project_copy,
)
from src.project_registration import register_session_in_project
from src.system_files import filter_system_files


@dataclass
class ProjectSave:
    copied_paths: list[str] = field(default_factory=list)  # relative to the project, the archived source included
    output_paths: list[Path] = field(default_factory=list)  # the converted files that arrived (not the archived source)
    datalad: dict | None = None
    registered_sessions: list[str] = field(default_factory=list)
    recipe_offset_summary: dict | None = None
    removed_stale: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def iter_session_registration_values(*, session_override: str | None, detected_sessions: list[str] | None) -> list[str]:
    """The sessions to register: the one given, or (for ``all``) every session the file turned out to hold."""
    normalized_override = str(session_override or "").strip()
    if not normalized_override:
        return []
    if normalized_override.lower() != "all":
        return [normalized_override]

    values: list[str] = []
    seen: set[str] = set()
    for raw_value in detected_sessions or []:
        candidate = str(raw_value or "").strip()
        if not candidate or candidate.lower() == "all" or candidate in seen:
            continue
        seen.add(candidate)
        values.append(candidate)
    return values


def plan_template_copies(modality: str, source_dir, tasks, project_root) -> list[tuple[Path, Path]]:
    """``(source, destination)`` pairs for the used tasks' templates the project's code/library lacks.

    ``source_dir`` is a library root (with a ``<modality>/`` subfolder) or that subfolder itself."""
    if not project_root or not tasks:
        return []
    source_dir = Path(source_dir)
    if (source_dir / modality).is_dir() and not list(source_dir.glob(f"{modality}-*.json")):
        source_dir = source_dir / modality
    dest_dir = Path(project_root) / "code" / "library" / modality
    pairs = []
    for task in tasks:
        src, dest = source_dir / f"{modality}-{task}.json", dest_dir / f"{modality}-{task}.json"
        if src.exists() and not dest.exists():
            pairs.append((src, dest))
    return pairs


def extract_tasks_from_output(output_root: Path) -> list[str]:
    """The task names in the BIDS-style file names under ``output_root``."""
    tasks = set()
    for file_path in Path(output_root).rglob("*"):
        if file_path.is_file() and "_task-" in file_path.name:
            match = re.search(r"_task-([a-zA-Z0-9]+)", file_path.name)
            if match:
                tasks.add(match.group(1))
    return sorted(tasks)


def cleanup_stale_tool_limesurvey_sidecars(
    *, copied_output_paths: list[Path], source_suffix: str, log_fn: Callable[[str, str], Any] | None = None
) -> list[Path]:
    """Remove stale tool-limesurvey sidecars for non-LimeSurvey imports.

    When converting non-LSA/LSS sources, older buggy runs may have left `*_tool-limesurvey_survey.{tsv,json}` files in
    project survey folders. If the current run does not emit such files, clean stale leftovers in the survey
    directories touched by this save.
    """
    if str(source_suffix or "").strip().lower() in {".lsa", ".lss"}:
        return []
    if any("_tool-limesurvey_survey" in path.name for path in copied_output_paths):
        return []

    removed: list[Path] = []
    for survey_dir in sorted({path.parent for path in copied_output_paths if path.parent.name == "survey"}):
        for pattern in ("*_tool-limesurvey_survey.tsv", "*_tool-limesurvey_survey.json"):
            for stale in survey_dir.glob(pattern):
                if not stale.is_file():
                    continue
                try:
                    stale.unlink()
                    removed.append(stale)
                except OSError:
                    continue
    if removed and callable(log_fn):
        log_fn(f"Removed {len(removed)} stale tool-limesurvey sidecar file(s) for non-LimeSurvey import.", "info")
    return removed


def save_conversion_to_project(
    *,
    project_root,
    staged_root,
    convert_result,
    source_path,
    source_name: str,
    session_override: str | None,
    template_version_overrides: Any,
    archive_sourcedata: bool = False,
    modality: str = "survey",
    run_message: str = "PRISM: Copy converted survey files into project",
    conv_type: str | None = None,
    extra_pairs: list[tuple[Path, Path]] | None = None,
    log_fn: Callable[[str, str], Any] | None = None,
) -> ProjectSave:
    """Save the files in ``staged_root`` (a conversion's output) into ``project_root``."""
    project_root, staged_root = Path(project_root), Path(staged_root)
    log = log_fn or (lambda message, level="info": None)

    log(f"Saving output to project: {project_root.name} (into project root)", "info")
    pairs: list[tuple[Path, Path]] = []
    for item in sorted(staged_root.rglob("*")):
        if item.is_file() and filter_system_files([item.name]):
            pairs.append((item, project_root / item.relative_to(staged_root)))
    output_rel = {dest.relative_to(project_root).as_posix() for _src, dest in pairs}
    pairs.extend(extra_pairs or [])  # e.g. the templates the conversion used: copied, but not "converted output"
    if archive_sourcedata and source_path:
        pairs.append((Path(source_path), project_root / "sourcedata" / source_name))

    copy_result = copy_files_into_project(dataset_root=project_root, copy_pairs=pairs, run_message=run_message)
    saved = ProjectSave(copied_paths=[str(p) for p in copy_result.get("copied_paths") or []], datalad=copy_result.get("datalad"))
    saved.output_paths = [project_root / rel for rel in saved.copied_paths if rel in output_rel]
    log("Project updated successfully!", "success")
    if archive_sourcedata:
        log(f"Archived original file to sourcedata/{source_name}", "info")

    suffix = Path(source_name).suffix.lower()
    if modality == "survey":
        saved.removed_stale = cleanup_stale_tool_limesurvey_sidecars(
            copied_output_paths=saved.output_paths,
            source_suffix=suffix,
            log_fn=log_fn,
        )

    sessions = iter_session_registration_values(
        session_override=session_override, detected_sessions=list(getattr(convert_result, "detected_sessions", []) or [])
    )
    if sessions:
        tasks = list(getattr(convert_result, "tasks_included", None) or extract_tasks_from_output(staged_root))
        label = conv_type or (f"{modality}-lsa" if suffix == ".lsa" else f"{modality}-xlsx")
        for session in sessions:
            register_session_in_project(
                project_root, session, tasks, modality, source_name, label, template_version_overrides=template_version_overrides
            )
        saved.registered_sessions = sessions
        log(f"Registered in project.json: {', '.join(sessions)} → {', '.join(tasks)}", "info")

    applied = getattr(convert_result, "applied_value_offsets", None) or {}
    if modality == "survey" and applied:
        from src.converters.survey import sync_project_survey_recipe_offsets

        try:
            summary = sync_project_survey_recipe_offsets(
                project_root=project_root,
                task_value_offsets=applied,
                offset_application_counts=getattr(convert_result, "value_offset_application_counts", {}) or {},
            )
            saved.recipe_offset_summary = summary
            if summary.get("updated_tasks"):
                log("Updated survey recipe offset metadata for: " + ", ".join(summary["updated_tasks"]), "info")
            if summary.get("missing_tasks"):
                log("No matching survey recipe file found for: " + ", ".join(summary["missing_tasks"]), "warning")
            for sync_error in summary.get("errors", []):
                log(f"Recipe offset sync warning: {sync_error}", "warning")
        except Exception as sync_error:  # noqa: BLE001 - the recipe metadata must never fail a conversion that was saved
            log(f"Recipe offset sync warning: {sync_error}", "warning")
    return saved


class ConversionCancelled(Exception):
    """The user cancelled while the converted files were being saved."""


def register_converted_physio_sessions(project_path, converted, dataset_name, log_fn=None) -> list[str]:
    """Register each converted (session, destination folder) in project.json; returns the session labels."""
    from collections import defaultdict

    session_tasks: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in converted:
        if item.success and item.session:
            tasks = session_tasks[(item.session, item.target_folder)]
            if item.task:
                tasks.append(item.task)
    registered: list[str] = []
    for (session, folder), tasks in session_tasks.items():
        tasks = sorted(set(tasks))
        try:
            register_session_in_project(Path(project_path), session, tasks, folder, dataset_name, "physio")
            registered.append(session)
            if log_fn:
                log_fn(f"Registered in project.json: ses-{session} ({folder}){' → ' + ', '.join(tasks) if tasks else ''}", "info")
        except Exception as error:  # noqa: BLE001 - a registration problem never fails a saved conversion
            if log_fn:
                log_fn(f"⚠️ Could not register session ses-{session} in project.json: {error}", "warning")
    return registered


def save_physio_batch_to_project(
    *,
    project_root,
    staged_root,
    converted,
    dataset_name: str,
    dest_root: str,
    flat_structure: bool,
    modality_filter: str,
    subject_rewrite_mode: str,
    run_message: str = "PRISM: Copy batch-converted physio files into project",
    cancel_check: Callable[[], bool] | None = None,
    log_fn: Callable[[str, str], Any] | None = None,
) -> ProjectSave:
    """Save a physio batch conversion into the project: every staged file goes to its destination
    (``dest_root``, flat or structured, subject labels rewritten) through the DataLad-aware copy, and the
    converted sessions are registered in ``project.json``."""
    project_root, staged_root = Path(project_root), Path(staged_root)
    target_root = resolve_project_copy_root(project_root, dest_root)
    pairs: list[tuple[Path, Path]] = []
    warnings: list[str] = []
    warned: set[str] = set()
    for item in sorted(staged_root.rglob("*")):
        if not item.is_file():
            continue
        if cancel_check and cancel_check():
            raise ConversionCancelled()
        rel = rewrite_subject_in_relative_path(item.relative_to(staged_root), subject_rewrite_mode)
        if should_use_flat_project_copy(dest_root, flat_structure):
            folder = modality_filter if modality_filter != "all" else "physio"
            pairs.append((item, target_root / folder / rel.name))
        else:
            pairs.append((item, target_root / rel))
            subject = re.search(r"(sub-[A-Za-z0-9]+)", rel.name)
            if subject and not (target_root / subject[1]).exists() and subject[1] not in warned:
                warned.add(subject[1])
                warnings.append(f"Subject folder {subject[1]} did not exist and will be created in project.")

    copy_result = copy_files_into_project(dataset_root=project_root, copy_pairs=pairs, run_message=run_message)
    saved = ProjectSave(
        copied_paths=[str(p) for p in copy_result.get("copied_paths") or []], datalad=copy_result.get("datalad"), warnings=warnings
    )
    saved.output_paths = [project_root / rel for rel in saved.copied_paths]
    saved.registered_sessions = register_converted_physio_sessions(project_root, converted, dataset_name, log_fn)
    return saved
