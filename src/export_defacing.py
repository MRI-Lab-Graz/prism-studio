"""Defacing for export: the report, the readiness check and the run, for ``export deface*`` and Studio's export page.

Defacing always targets an export copy and never mutates the source project: with a DataLad dataset and the
datalad-preserving mode the copy is a DataLad clone defaced through ``datalad run``; otherwise the anatomical scans
are copied (keeping their relative structure) to a target folder and defaced there.
"""

from __future__ import annotations

from pathlib import Path

from src.export_options import normalize_defacing_variant_keys, normalize_scope_labels


def _counts(report) -> dict:
    counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
    for entry in report:
        status = entry.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def defacing_report(project_path, data: dict) -> dict:
    """Defacing status of every anatomical scan in the project (or the selected variants and scope)."""
    from src.mri_json_scrubber import build_defacing_report

    report = build_defacing_report(
        Path(project_path),
        selected_variants=normalize_defacing_variant_keys(data.get("selected_variants")),
        excluded_subjects=normalize_scope_labels(data.get("exclude_subjects")) or None,
        excluded_sessions=normalize_scope_labels(data.get("exclude_sessions")) or None,
    )
    return {"success": True, "report": report, "counts": _counts(report)}


def defacing_preflight(project_path) -> dict:
    """Whether defacing can run for this project in this environment."""
    from src.mri_json_scrubber import get_defacing_preflight

    return {"success": True, **get_defacing_preflight(Path(project_path))}


def run_defacing(project_path, data: dict) -> tuple[dict, bool]:
    """Deface an export copy of the project; returns ``(payload, succeeded)``."""
    from src.mri_json_scrubber import build_defacing_report, deface_anatomical_scans, prepare_defacing_export_copy
    from src.project_manager import ProjectManager

    project = Path(project_path)
    selected_variants = normalize_defacing_variant_keys(data.get("selected_variants"))
    excluded_subjects = normalize_scope_labels(data.get("exclude_subjects")) or None
    excluded_sessions = normalize_scope_labels(data.get("exclude_sessions")) or None
    mode_raw = str(data.get("repository_mode") or "").strip().lower()
    mode = mode_raw if mode_raw in {"datalad_free", "datalad_preserving"} else "datalad_preserving"
    output_folder = str(data.get("output_folder") or "").strip()

    datalad_status = ProjectManager().get_datalad_status(project)
    datalad_enabled = bool(datalad_status.get("enabled"))
    preserve_datalad = datalad_enabled if not mode_raw else mode == "datalad_preserving" and datalad_enabled
    output_root = Path(output_folder).expanduser().resolve(strict=False) if output_folder else project.parent

    copy_summary = prepare_defacing_export_copy(
        project, output_root, selected_variants=selected_variants, excluded_subjects=excluded_subjects,
        excluded_sessions=excluded_sessions, preserve_datalad_metadata=preserve_datalad,
        datalad_executable=str(datalad_status.get("executable") or ""),
    )
    if not copy_summary.get("success"):
        return {
            "success": False,
            "error": str(copy_summary.get("error") or "Could not prepare export defacing copy."),
            "target_mode": "export_copy",
            "source_project_path": str(project),
            "target_path": str(copy_summary.get("target_path") or ""),
        }, False

    target_path = Path(str(copy_summary.get("target_path") or "")).resolve(strict=False)
    result = deface_anatomical_scans(
        target_path, force=bool(data.get("force", False)), selected_variants=selected_variants,
        excluded_subjects=excluded_subjects, excluded_sessions=excluded_sessions,
    )
    post_report = build_defacing_report(
        target_path, selected_variants=selected_variants, excluded_subjects=excluded_subjects, excluded_sessions=excluded_sessions
    )
    counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
    for entry in post_report:
        status = str(entry.get("status", "unknown"))
        counts[status if status in counts else "unknown"] += 1

    payload = {
        "success": bool(result.get("success", False)),
        "message": result.get("message") or result.get("error") or "",
        "error": result.get("error"),
        "defacing": {"counts": result.get("counts") or {}, "items": result.get("items") or []},
        "datalad": result.get("datalad") or {},
        "target_mode": "export_copy",
        "target_path": str(target_path),
        "source_project_path": str(project),
        "copy_summary": copy_summary or {},
        "report": post_report,
        "report_counts": counts,
    }
    if payload["success"]:
        payload["message"] = f"{payload['message']} Source project was not modified; defaced copy written to {target_path}."
    return payload, payload["success"]
