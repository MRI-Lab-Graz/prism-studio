import os
from pathlib import Path

from flask import jsonify, render_template

from src.biosample_template import specimen_types
from src.recipe_builder import list_run_modalities

from .tools_helpers import _default_library_root_for_templates, _global_recipes_root


def handle_converter(project_path: str | None):
    default_library_path = None
    if project_path:
        candidate = (Path(project_path) / "code" / "library").expanduser()
        if candidate.exists() and candidate.is_dir():
            default_library_path = candidate
        else:
            candidate = (Path(project_path) / "library").expanduser()
            if candidate.exists() and candidate.is_dir():
                default_library_path = candidate

    if default_library_path is None:
        default_library_path = _default_library_root_for_templates(modality="survey")

    participants_mapping_info = None
    if project_path:
        project_root = Path(project_path)
        mapping_candidates = [
            project_root / "code" / "library" / "participants_mapping.json",
            project_root / "sourcedata" / "participants_mapping.json",
        ]
        for candidate in mapping_candidates:
            if candidate.exists():
                participants_mapping_info = {
                    "path": str(candidate),
                    "status": "found",
                    "message": f"Found participants_mapping.json at {candidate.relative_to(project_root)}",
                }
                break

        if not participants_mapping_info:
            participants_mapping_info = {
                "path": str(
                    project_root / "code" / "library" / "participants_mapping.json"
                ),
                "status": "not_found",
                "message": "No participants_mapping.json found. Create one to auto-transform demographic data.",
            }

    return render_template(
        "converter.html",
        default_survey_library_path=str(default_library_path or ""),
        participants_mapping_info=participants_mapping_info,
        biosample_specimen_types=specimen_types(),
    )


def handle_recipes(project_path: str):
    offered = list_run_modalities(project_path, _global_recipes_root())
    return render_template(
        "recipes.html",
        available_modalities=offered["modalities"],
        default_modality=offered["default"],
    )


def handle_recipe_builder(project_path: str):
    return render_template("recipe_builder.html")


def handle_api_recipes_sessions(dataset_path: str):
    if not dataset_path or not os.path.isdir(dataset_path):
        return jsonify({"sessions": []}), 200

    roots = [Path(dataset_path)]

    session_ids: set[str] = set()
    for root in roots:
        for ses_path in root.glob("sub-*/ses-*"):
            if ses_path.is_dir():
                session_ids.add(ses_path.name)

    return jsonify({"sessions": sorted(session_ids)}), 200


def handle_api_recipes_modalities(dataset_path: str):
    """Return available recipe modalities for a given project path (for post-run refresh)."""
    return jsonify(list_run_modalities(dataset_path, _global_recipes_root())), 200
