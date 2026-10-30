"""``prism_tools.py export ...``: Studio's export page as commands (thin adapters over ``src.export_options``)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.export_options import ExportBlocked, export_zip_name, normalize_export_preset, run_project_export


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
