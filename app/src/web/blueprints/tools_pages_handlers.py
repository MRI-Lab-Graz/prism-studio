import os
from pathlib import Path

from flask import jsonify, render_template

from .tools_helpers import _default_library_root_for_templates


def _detect_available_recipe_modalities(project_root: Path) -> tuple[list[dict], str]:
    """Detect recipe modalities available for the current project."""
    roots = [project_root]
    rawdata_root = project_root / "rawdata"
    if rawdata_root.is_dir():
        roots.append(rawdata_root)

    def _has_data(modality: str) -> bool:
        for root in roots:
            if modality == "survey":
                for folder in ("survey", "beh"):
                    if any(root.glob(f"sub-*/ses-*/{folder}/*.tsv")):
                        return True
                    if any(root.glob(f"sub-*/{folder}/*.tsv")):
                        return True
            elif modality == "biometrics":
                if any(root.glob("sub-*/ses-*/biometrics/*.tsv")):
                    return True
                if any(root.glob("sub-*/biometrics/*.tsv")):
                    return True
        return False

    def _has_recipes(modality: str) -> bool:
        candidates = [
            project_root / "code" / "recipes" / modality,
            project_root / "recipe" / modality,
            project_root / "official" / "recipes" / modality,
        ]
        for folder in candidates:
            if folder.is_dir() and any(folder.glob("*.json")):
                return True
        return False

    modality_labels = {
        "survey": "Survey",
        "biometrics": "Biometrics",
    }

    available: list[dict] = []
    for modality in ("survey", "biometrics"):
        if _has_data(modality) and _has_recipes(modality):
            available.append({"value": modality, "label": modality_labels[modality]})

    if not available:
        available = [{"value": "survey", "label": "Survey"}]

    default_modality = available[0]["value"]
    return available, default_modality


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
                "path": str(project_root / "code" / "library" / "participants_mapping.json"),
                "status": "not_found",
                "message": "No participants_mapping.json found. Create one to auto-transform demographic data.",
            }

    return render_template(
        "converter.html",
        default_survey_library_path=str(default_library_path or ""),
        participants_mapping_info=participants_mapping_info,
    )


def handle_recipes(project_path: str):
    available_modalities = [{"value": "survey", "label": "Survey"}]
    default_modality = "survey"

    if project_path and Path(project_path).is_dir():
        available_modalities, default_modality = _detect_available_recipe_modalities(
            Path(project_path)
        )

    return render_template(
        "recipes.html",
        available_modalities=available_modalities,
        default_modality=default_modality,
    )


def handle_api_recipes_sessions(dataset_path: str):
    if not dataset_path or not os.path.isdir(dataset_path):
        return jsonify({"sessions": []}), 200

    roots = [Path(dataset_path)]
    rawdata_path = Path(dataset_path) / "rawdata"
    if rawdata_path.is_dir():
        roots.append(rawdata_path)

    session_ids: set[str] = set()
    for root in roots:
        for ses_path in root.glob("sub-*/ses-*"):
            if ses_path.is_dir():
                session_ids.add(ses_path.name)

    return jsonify({"sessions": sorted(session_ids)}), 200