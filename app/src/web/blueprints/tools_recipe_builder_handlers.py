"""Handlers for the Recipe Builder page.

These endpoints support creating and editing survey or biometrics recipe JSON
files interactively in the browser, without touching the recipe *runner* logic.
"""

import os
from pathlib import Path

from flask import jsonify

from src.constants import SUPPORTED_MODALITIES as _SUPPORTED_MODALITIES
from src.recipe_builder import (  # noqa: F401 - RecipeSaveError re-exported
    RecipeSaveError,
    draft_from_template,
    list_builder_templates,
    load_recipe,
    save_recipe_to_project,
)
from .tools_helpers import _global_survey_library_root


def _global_library_root() -> Path | None:
    """Return the global template library root (same resolution as the Template Editor)."""
    try:
        return _global_survey_library_root()
    except RuntimeError:  # no app context
        return None


# ---------------------------------------------------------------------------
# Public handlers
# ---------------------------------------------------------------------------


def handle_api_recipe_builder_surveys(
    dataset_path: str,
    include_global: bool = False,
    modality: str = "survey",
):
    """Return list of modality template JSON files available in the project.

    Pass ``include_global=True`` to also include the official PRISM library.
    """
    modality = (modality or "survey").strip().lower()
    if modality not in _SUPPORTED_MODALITIES:
        return jsonify({"error": "Invalid modality"}), 400

    if not dataset_path or not os.path.isdir(dataset_path):
        return jsonify({"surveys": []}), 200

    return (
        jsonify(
            {
                "surveys": list_builder_templates(
                    dataset_path, modality=modality, include_global=include_global, global_root=_global_library_root()
                ),
                "include_global": include_global,
                "modality": modality,
            }
        ),
        200,
    )


def handle_api_recipe_builder_items(
    dataset_path: str,
    task: str,
    include_global: bool = False,
    modality: str = "survey",
):
    """Return item IDs for a given task, extracted from a modality template JSON."""
    modality = (modality or "survey").strip().lower()
    if modality not in _SUPPORTED_MODALITIES:
        return jsonify({"error": "Invalid modality"}), 400

    if not dataset_path or not task:
        return jsonify({"items": []}), 200
    if not os.path.isdir(dataset_path):
        return jsonify({"error": "Project path not found"}), 400

    return (
        jsonify(
            draft_from_template(
                dataset_path, task, modality=modality, include_global=include_global, global_root=_global_library_root()
            )
        ),
        200,
    )


def handle_api_recipe_builder_load(
    dataset_path: str,
    task: str,
    modality: str = "survey",
):
    """Load an existing recipe JSON for the given task (if one exists)."""
    modality = (modality or "survey").strip().lower()
    if modality not in _SUPPORTED_MODALITIES:
        return jsonify({"error": "Invalid modality"}), 400

    if not dataset_path or not task:
        return jsonify({"recipe": None}), 200

    try:
        found = load_recipe(dataset_path, task, modality=modality)
    except RecipeSaveError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to parse recipe: {exc}"}), 500
    if found is None:
        return jsonify({"recipe": None}), 200
    return jsonify({"recipe": found[0], "path": str(found[1])}), 200


def handle_api_recipe_builder_save(data: dict):
    """Save a recipe JSON to the project's code/recipes/{modality} folder."""
    try:
        result = save_recipe_to_project(
            (data.get("dataset_path") or "").strip(),
            data.get("recipe"),
            modality=data.get("modality"),
            global_root=_global_library_root(),
        )
    except RecipeSaveError as exc:
        payload: dict[str, object] = {"error": str(exc)}
        if exc.validation_errors:
            payload["validation_errors"] = exc.validation_errors
        return jsonify(payload), 400
    except OSError as exc:
        return jsonify({"error": f"Failed to write recipe: {exc}"}), 500
    return jsonify(result), 200
