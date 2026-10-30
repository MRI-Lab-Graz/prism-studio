"""``prism_tools.py export ...``: Studio's export page as commands (thin adapters over ``src.export_options``)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.export_options import (
    ExportBlocked,
    export_zip_name,
    normalize_export_preset,
    run_annex_availability,
    run_folder_export,
    run_git_lfs_export,
    run_project_export,
)


def _grouped(values) -> dict[str, list[str]]:
    """``["anat=a", "anat=b", "func=rest"]`` -> ``{"anat": ["a", "b"], "func": ["rest"]}``."""
    grouped: dict[str, list[str]] = {}
    for value in values or []:
        group, _, label = str(value).partition("=")
        if group.strip() and label.strip():
            grouped.setdefault(group.strip(), []).append(label.strip())
    return grouped


def export_data_from_args(args) -> dict:
    """The options dict Studio's export page sends, built from the command's flags."""
    return {
        "anonymize": not getattr(args, "no_anonymize", False),
        "mask_questions": not getattr(args, "no_mask_questions", False),
        "export_preset": getattr(args, "preset", "standard"),
        "include_derivatives": not getattr(args, "no_derivatives", False),
        "include_sourcedata": bool(getattr(args, "include_sourcedata", False)),
        "include_code": not getattr(args, "no_code", False),
        "include_analysis": bool(getattr(args, "include_analysis", False)),
        "exclude_subjects": list(getattr(args, "exclude_subject", None) or []),
        "exclude_sessions": list(getattr(args, "exclude_session", None) or []),
        "exclude_modalities": list(getattr(args, "exclude_modality", None) or []),
        "exclude_acq": _grouped(getattr(args, "exclude_acq", None)),
        "exclude_tasks": _grouped(getattr(args, "exclude_task", None)),
        "scrub_mri_json": bool(getattr(args, "scrub_mri_json", False)),
        "scrub_mri_json_groups": list(getattr(args, "scrub_group", None) or []),
        "export_phenotype_bridge": bool(getattr(args, "phenotype_bridge", False)),
        "repository_mode": getattr(args, "repository_mode", None),
        "validation_mode": getattr(args, "validation_mode", "both"),
        "output_folder": getattr(args, "output_folder", None),
        "materialize_annex_content": bool(getattr(args, "materialize_annex_content", False)),
        "init_git_lfs_repo": not getattr(args, "no_init_repo", False),
    }


def cmd_export_project(args) -> None:
    project = Path(args.project).resolve()
    if project.is_file():
        project = project.parent
    if not project.is_dir():
        print(f"Error: project folder not found: {project}")
        sys.exit(1)
    data = export_data_from_args(args)
    destination = Path(args.output_folder).expanduser() if getattr(args, "output_folder", None) else project.parent
    destination.mkdir(parents=True, exist_ok=True)
    output_zip = destination / export_zip_name(project.name, data["anonymize"], normalize_export_preset(data["export_preset"]))

    def progress(percent: int, message: str) -> None:
        print(f"[{percent:3d}%] {message}")

    try:
        run_project_export(project, output_zip, data, progress_callback=progress)
    except ExportBlocked as exc:
        output_zip.unlink(missing_ok=True)
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - a failed export leaves no half-written zip
        output_zip.unlink(missing_ok=True)
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"✅ Exported to {output_zip}")


def cmd_export_folder(args) -> None:
    """Export the project to a plain folder without Git/DataLad metadata (the folder export of Studio's page)."""
    project = Path(args.project).resolve()
    project = project.parent if project.is_file() else project
    if not project.is_dir():
        print(f"Error: project folder not found: {project}")
        sys.exit(1)
    result = run_folder_export(project, export_data_from_args(args))
    if not result.get("success"):
        print(f"Error: {result.get('error') or 'folder export failed'}")
        sys.exit(1)
    print(f"✅ Exported to {result.get('output_path') or result.get('output_root') or args.output_folder or 'the default folder'}")


def _project_or_exit(args) -> Path:
    project = Path(args.project).resolve()
    project = project.parent if project.is_file() else project
    if not project.is_dir():
        print(f"Error: project folder not found: {project}")
        sys.exit(1)
    return project


def _print_result(result: dict, args, done: str) -> None:
    import json

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif result.get("success"):
        print(f"✅ {done}")
    if not result.get("success"):
        print(f"Error: {result.get('error') or 'failed'}")
        sys.exit(1)


def cmd_export_git_lfs(args) -> None:
    """A one-way Git LFS export snapshot: a folder, and by default an initialized repository."""
    result = run_git_lfs_export(_project_or_exit(args), export_data_from_args(args))
    _print_result(result, args, f"Exported to {result.get('output_path') or result.get('output_root') or 'the default folder'}")


def cmd_export_annex_availability(args) -> None:
    """Which files of the export scope are missing locally (git-annex content not fetched)."""
    result = run_annex_availability(_project_or_exit(args), export_data_from_args(args))
    _print_result(result, args, "Availability checked")


def cmd_export_structure(args) -> None:
    """The sessions and modalities an export can be scoped to."""
    import json

    from src.project_structure import get_project_modalities_and_sessions

    print(json.dumps(get_project_modalities_and_sessions(_project_or_exit(args)), indent=2, default=str))


def _emit(payload: dict, ok: bool = True) -> None:
    import json

    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    if not ok:
        sys.exit(1)


def _defacing_data(args) -> dict:
    return {
        "selected_variants": list(getattr(args, "selected_variant", None) or []) or None,
        "exclude_subjects": list(getattr(args, "exclude_subject", None) or []),
        "exclude_sessions": list(getattr(args, "exclude_session", None) or []),
        "repository_mode": getattr(args, "repository_mode", None),
        "output_folder": getattr(args, "output_folder", None),
        "force": bool(getattr(args, "force", False)),
    }


def cmd_export_deface_report(args) -> None:
    """Defacing status of every anatomical scan (JSON, as Studio's export page shows it)."""
    from src.export_defacing import defacing_report

    _emit(defacing_report(_project_or_exit(args), _defacing_data(args)))


def cmd_export_deface_preflight(args) -> None:
    """Whether defacing can run here (JSON)."""
    from src.export_defacing import defacing_preflight

    _emit(defacing_preflight(_project_or_exit(args)))


def cmd_export_deface(args) -> None:
    """Deface an export COPY of the project (never the project itself); prints the result as JSON."""
    from src.export_defacing import run_defacing

    payload, ok = run_defacing(_project_or_exit(args), _defacing_data(args))
    _emit(payload, ok)
