"""The export's options dict built from command flags; shared by `export` and `datalad get-data`."""

from __future__ import annotations


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
