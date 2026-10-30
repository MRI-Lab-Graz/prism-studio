"""Exporting a project: the options, the validation gate and the run, for ``prism_tools.py export project`` and Studio.

Studio's export page only collects the options and shows progress; what an option means (the upload-ready preset, the
repository mode, the scope filters), the validation that blocks an export and the export itself are here.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

from src.project_export import export_project

EXPORT_VALIDATION_MODES = {"both", "bids", "prism", "ignore", "none"}
EXPORT_PRESETS = {"standard", "upload_ready"}
EXPORT_REPOSITORY_MODES = {"datalad_free", "datalad_preserving", "git_lfs"}


class ExportBlocked(Exception):
    """Validation found errors, so nothing was exported; the message says what to do."""


def normalize_export_validation_mode(raw_mode: object) -> str:
    mode = str(raw_mode or "").strip().lower()
    if mode not in EXPORT_VALIDATION_MODES:
        return "both"
    return "ignore" if mode == "none" else mode


def normalize_export_preset(raw_preset: object) -> str:
    preset = str(raw_preset or "").strip().lower()
    return preset if preset in EXPORT_PRESETS else "standard"


def export_validation_flags(validation_mode: str) -> tuple[bool, bool]:
    """``(run_bids, run_prism)`` for a validation mode."""
    mode = normalize_export_validation_mode(validation_mode)
    if mode == "bids":
        return True, False
    if mode == "prism":
        return False, True
    if mode == "ignore":
        return False, False
    return True, True


def export_validation_mode_label(validation_mode: str) -> str:
    return {"bids": "BIDS", "prism": "PRISM", "ignore": "validation"}.get(normalize_export_validation_mode(validation_mode), "PRISM + BIDS")


def resolve_exclude_version_control_metadata(data: dict, *, export_preset: str) -> bool:
    """Whether a ZIP export strips Git/DataLad metadata.

    ``repository_mode`` (datalad_free / datalad_preserving / git_lfs) is authoritative when present: only
    ``datalad_preserving`` keeps repository metadata. Falls back to the older ``exclude_version_control_metadata`` flag.
    The upload-ready preset always strips it.
    """
    mode = str(data.get("repository_mode") or "").strip().lower()
    exclude = mode != "datalad_preserving" if mode in EXPORT_REPOSITORY_MODES else bool(data.get("exclude_version_control_metadata", False))
    return True if export_preset == "upload_ready" else exclude


def normalize_scrub_group_ids(raw_groups: object) -> Optional[Set[str]]:
    if not isinstance(raw_groups, (list, tuple, set)):
        return None
    return {str(group).strip().lower() for group in raw_groups if str(group).strip()} or None


def normalize_defacing_variant_keys(raw_values: object) -> Optional[Set[str]]:
    """Selected defacing variant keys (``None`` when none were given)."""
    if not isinstance(raw_values, (list, tuple, set)):
        return None
    return {str(value).strip().lower() for value in raw_values if str(value).strip()}


def normalize_scope_labels(raw_values: object) -> Set[str]:
    if not isinstance(raw_values, (list, tuple, set)):
        return set()
    return {str(value).strip() for value in raw_values if str(value).strip()}


def normalize_scope_grouped_labels(raw_values: object) -> Dict[str, Set[str]]:
    if not isinstance(raw_values, dict):
        return {}
    grouped = {str(name).strip(): normalize_scope_labels(labels) for name, labels in raw_values.items() if str(name).strip()}
    return {name: labels for name, labels in grouped.items() if labels}


def build_export_kwargs(data: dict) -> dict:
    """The arguments of ``project_export.export_project`` (without the paths) for an options dict."""
    preset = normalize_export_preset(data.get("export_preset", "standard"))
    scrub_mri_json = bool(data.get("scrub_mri_json", False))
    upload_ready = preset == "upload_ready"
    return {
        "anonymize": bool(data.get("anonymize", True)),
        "mask_questions": bool(data.get("mask_questions", True)),
        "id_length": 8,  # fixed deterministic IDs when anonymizing
        "deterministic": True,
        "include_derivatives": False if upload_ready else bool(data.get("include_derivatives", True)),
        "include_sourcedata": False if upload_ready else bool(data.get("include_sourcedata", False)),
        "include_code": False if upload_ready else bool(data.get("include_code", True)),
        "include_analysis": False if upload_ready else bool(data.get("include_analysis", False)),
        "exclude_subjects": normalize_scope_labels(data.get("exclude_subjects")) or None,
        "exclude_sessions": normalize_scope_labels(data.get("exclude_sessions")) or None,
        "exclude_modalities": normalize_scope_labels(data.get("exclude_modalities")) or None,
        "exclude_acq": normalize_scope_grouped_labels(data.get("exclude_acq")) or None,
        "exclude_tasks": normalize_scope_grouped_labels(data.get("exclude_tasks")) or None,
        "exclude_version_control_metadata": resolve_exclude_version_control_metadata(data, export_preset=preset),
        "scrub_mri_json": scrub_mri_json,
        "scrub_mri_json_groups": normalize_scrub_group_ids(data.get("scrub_mri_json_groups")),
        "clean_nifti_gzip_headers": scrub_mri_json,
        "export_phenotype_bridge": bool(data.get("export_phenotype_bridge", False)),
    }


def export_zip_name(project_name: str, anonymize: bool, export_preset: str) -> str:
    return f"{project_name}{'_anonymized' if anonymize else ''}{'_upload_ready' if normalize_export_preset(export_preset) == 'upload_ready' else ''}_export.zip"


def count_validation_issues(issues: object, *, dataset_stats: object, dataset_path: Path, run_bids: bool, run_prism: bool) -> tuple[int, int]:
    # Reuse the Validation page's formatting and filtering, so an export is blocked by what users see there.
    # ponytail: these two helpers still live in Studio's tree (app/src/web); move them into src/ with the validation backend.
    from src.web.blueprints.validation import _apply_validation_mode_issue_filter
    from src.web.utils import format_validation_results

    results = format_validation_results(list(issues) if isinstance(issues, (list, tuple)) else [], dataset_stats, str(dataset_path))
    results = _apply_validation_mode_issue_filter(results, run_bids=run_bids, run_prism=run_prism)
    summary = results.get("summary", {}) if isinstance(results, dict) else {}
    return int(summary.get("total_errors", 0) or 0), int(summary.get("total_warnings", 0) or 0)


def run_pre_export_validation(project_path: Path, validation_mode: str) -> str | None:
    """The reason an export is blocked (validation errors), or ``None`` when it may go ahead."""
    run_bids, run_prism = export_validation_flags(validation_mode)
    if not run_bids and not run_prism:
        return None
    from src.web.validation import run_validation  # ponytail: see count_validation_issues

    issues, dataset_stats = run_validation(
        str(project_path), verbose=True, schema_version="stable", run_bids=run_bids, run_prism=run_prism, project_path=str(project_path)
    )
    errors, warnings = count_validation_issues(issues, dataset_stats=dataset_stats, dataset_path=project_path, run_bids=run_bids, run_prism=run_prism)
    if errors == 0:
        return None
    warning_suffix = f" ({warnings} {'warning' if warnings == 1 else 'warnings'} also reported)" if warnings else ""
    return (
        f"Export blocked: validation found {errors} {'error' if errors == 1 else 'errors'} "
        f"in {export_validation_mode_label(validation_mode)} checks{warning_suffix}. "
        "Fix the validation errors or choose 'Ignore validation' in the export options."
    )


def build_export_defacing_warning(project_path: Path, exclude_subjects=None, exclude_sessions=None) -> Optional[dict]:
    """Warning-only summary of anatomical scans in the exported scope that are not defaced (never blocks)."""
    try:
        from src.mri_json_scrubber import build_defacing_report

        report = build_defacing_report(
            project_path, excluded_subjects=set(exclude_subjects or []), excluded_sessions=set(exclude_sessions or [])
        )
    except Exception:  # noqa: BLE001 - a warning must never fail an export
        return None
    counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
    for entry in report:
        status = str(entry.get("status", "unknown"))
        counts[status if status in counts else "unknown"] += 1
    risk = counts["not_defaced"] + counts["unknown"]
    if risk <= 0:
        return None
    return {
        "message": (
            f"This export includes {risk} anatomical {'scan' if risk == 1 else 'scans'} that are not defaced. "
            "This dataset is not ready for public sharing until defacing is completed. "
            "Export continued because this is warning-only."
        ),
        "counts": counts,
        "risk_count": risk,
    }


def run_project_export(
    project_path,
    output_zip,
    data: dict,
    *,
    progress_callback: Callable[[int, str], Any] | None = None,
    cancelled_flag: threading.Event | None = None,
) -> None:
    """Validate (unless ignored), then export the project to ``output_zip``.

    Raises ExportBlocked (validation errors) or InterruptedError (cancelled)."""
    project_path = Path(project_path)
    say = progress_callback or (lambda percent, message: None)

    def cancelled() -> bool:
        return bool(cancelled_flag is not None and cancelled_flag.is_set())

    if cancelled():
        raise InterruptedError("Export cancelled by user")
    mode = normalize_export_validation_mode(data.get("validation_mode", "both"))
    if any(export_validation_flags(mode)):
        say(2, f"Running {export_validation_mode_label(mode)} validation before export...")
        if blocked := run_pre_export_validation(project_path, mode):
            raise ExportBlocked(blocked)
        if cancelled():
            raise InterruptedError("Export cancelled by user")
        say(5, "Validation passed. Starting export...")
    export_project(
        project_path=project_path,
        output_zip=Path(output_zip),
        **build_export_kwargs(data),
        progress_callback=progress_callback,
        cancelled_flag=cancelled_flag,
    )


_SCOPE_KEYS = ("include_derivatives", "include_sourcedata", "include_code", "include_analysis", "exclude_subjects",
               "exclude_sessions", "exclude_modalities", "exclude_acq", "exclude_tasks")


def _folder_scope(data: dict) -> dict:
    """The include/exclude scope of the folder-style exports, with their defaults (analysis is on here)."""
    scope = {
        "include_derivatives": bool(data.get("include_derivatives", True)),
        "include_sourcedata": bool(data.get("include_sourcedata", False)),
        "include_code": bool(data.get("include_code", True)),
        "include_analysis": bool(data.get("include_analysis", True)),
        "exclude_sessions": normalize_scope_labels(data.get("exclude_sessions")) or None,
        "exclude_modalities": normalize_scope_labels(data.get("exclude_modalities")) or None,
        "exclude_acq": normalize_scope_grouped_labels(data.get("exclude_acq")) or None,
        "exclude_tasks": normalize_scope_grouped_labels(data.get("exclude_tasks")) or None,
    }
    if "exclude_subjects" in data:
        scope["exclude_subjects"] = normalize_scope_labels(data.get("exclude_subjects")) or None
    return scope


def _folder_kwargs(data: dict, extra_scope_keys: tuple = ()) -> dict:
    """What the folder-style exports share: the output, MRI scrubbing, the phenotype bridge, and the scope when sent."""
    kwargs: Dict[str, Any] = {"output_root": data.get("output_folder") or None}
    if "scrub_mri_json" in data:
        kwargs["scrub_mri_json"] = bool(data.get("scrub_mri_json", False))
        if kwargs["scrub_mri_json"]:
            kwargs["scrub_mri_json_groups"] = normalize_scrub_group_ids(data.get("scrub_mri_json_groups"))
    if "export_phenotype_bridge" in data:
        kwargs["export_phenotype_bridge"] = bool(data.get("export_phenotype_bridge", False))
    if any(key in data for key in (*_SCOPE_KEYS, *extra_scope_keys)):
        kwargs.update(_folder_scope(data))
    return kwargs


def build_folder_export_kwargs(data: dict) -> dict:
    """The arguments of ``ProjectManager.export_project_to_plain_folder`` for an options dict.

    Only what was sent is passed on; any scope option brings the folder export's own defaults with it."""
    kwargs = _folder_kwargs(data, ("materialize_annex_content",))
    if "include_derivatives" in kwargs:  # the scope was sent, so the folder export's own defaults apply
        kwargs["materialize_annex_content"] = bool(data.get("materialize_annex_content", False))
    return kwargs


def build_git_lfs_export_kwargs(data: dict) -> dict:
    """The arguments of ``ProjectManager.export_project_to_git_lfs_folder``."""
    return {**_folder_kwargs(data), "init_git_lfs_repo": bool(data.get("init_git_lfs_repo", True))}


def build_annex_availability_kwargs(data: dict) -> dict:
    """The arguments of ``ProjectManager.preview_plain_folder_export_availability``: the scope is always sent."""
    return _folder_scope(data)


def run_folder_export(project_path, data: dict) -> dict:
    """Export the project to a plain folder (no Git/DataLad metadata); returns the manager's result dict."""
    from src.project_manager import ProjectManager

    return ProjectManager().export_project_to_plain_folder(Path(project_path), **build_folder_export_kwargs(data))


def run_git_lfs_export(project_path, data: dict) -> dict:
    from src.project_manager import ProjectManager

    return ProjectManager().export_project_to_git_lfs_folder(Path(project_path), **build_git_lfs_export_kwargs(data))


def run_annex_availability(project_path, data: dict) -> dict:
    from src.project_manager import ProjectManager

    return ProjectManager().preview_plain_folder_export_availability(Path(project_path), **build_annex_availability_kwargs(data))
