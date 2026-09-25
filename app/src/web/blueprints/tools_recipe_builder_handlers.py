"""Handlers for the Recipe Builder page.

These endpoints support creating and editing survey or biometrics recipe JSON
files interactively in the browser, without touching the recipe *runner* logic.
"""

import json
import os
import re
from pathlib import Path

from flask import current_app, jsonify

from src.constants import SUPPORTED_MODALITIES as _SUPPORTED_MODALITIES
from src.recipe_builder import (  # noqa: F401 - RecipeSaveError re-exported
    RecipeSaveError,
    detect_scale_ranges,
    extract_item_description_metadata_from_template,
    extract_item_ranges_from_template,
    extract_items_from_template,
    extract_items_missing_ranges_from_template,
    extract_template_reversed_items,
    find_templates,
    save_recipe_to_project,
)


def _global_library_root() -> Path | None:
    """Return the global template library root (mirrors tools_helpers logic)."""
    try:
        base_dir = Path(current_app.root_path)
        for candidate in [
            base_dir / "official" / "library",
            base_dir.parent / "official" / "library",
        ]:
            try:
                resolved = candidate.resolve()
                if resolved.exists() and resolved.is_dir():
                    return resolved
            except (OSError, ValueError):
                if candidate.exists() and candidate.is_dir():
                    return candidate
        return None
    except RuntimeError:
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

    templates = find_templates(
        dataset_path,
        modality=modality,
        include_global=include_global,
        global_root=_global_library_root(),
    )
    client = [
        {
            "task": t["task"],
            "label": t["label"],
            "file": t["file"],
            "source": t["source"],
        }
        for t in templates
    ]
    return (
        jsonify(
            {
                "surveys": client,
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

    templates = find_templates(
        dataset_path,
        modality=modality,
        include_global=include_global,
        global_root=_global_library_root(),
    )
    match = next((t for t in templates if t["task"] == task), None)
    if match is None:
        return jsonify({"items": []}), 200

    items = extract_items_from_template(match["full_path"], modality=modality)
    (
        item_descriptions,
        item_descriptions_i18n,
        item_description_languages,
        template_language,
    ) = extract_item_description_metadata_from_template(
        match["full_path"],
        modality=modality,
    )
    scale_ranges = detect_scale_ranges(match["full_path"], modality=modality)
    item_ranges = extract_item_ranges_from_template(match["full_path"], modality=modality)
    template_reversed_items = extract_template_reversed_items(
        match["full_path"],
        modality=modality,
    )
    items_missing_ranges = extract_items_missing_ranges_from_template(
        match["full_path"],
        modality=modality,
    )
    return (
        jsonify(
            {
                "items": items,
                "item_descriptions": item_descriptions,
                "item_descriptions_i18n": item_descriptions_i18n,
                "item_description_languages": item_description_languages,
                "template_language": template_language,
                "scale_ranges": scale_ranges,
                "item_ranges": item_ranges,
                "template_reversed_items": template_reversed_items,
                "items_missing_ranges": items_missing_ranges,
            }
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

    # Same restriction handle_api_recipe_builder_save applies before writing
    # -- task feeds straight into a filesystem path below, so reject anything
    # containing a path separator or other unexpected character rather than
    # silently returning {"recipe": None} for a malformed value.
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", task):
        return jsonify({"error": "Invalid task"}), 400

    candidates: list[Path] = [
        Path(dataset_path) / "code" / "recipes" / modality / f"recipe-{task}.json",
        Path(dataset_path)
        / "code"
        / "recipes"
        / modality
        / f"recipe-{task}_{modality}.json",
        Path(dataset_path) / "recipe" / modality / f"recipe-{task}.json",
        Path(dataset_path) / "recipe" / modality / f"recipe-{task}_{modality}.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                with open(candidate, encoding="utf-8") as fh:
                    data = json.load(fh)
                return jsonify({"recipe": data, "path": str(candidate)}), 200
            except Exception as exc:
                return jsonify({"error": f"Failed to parse recipe: {exc}"}), 500

    return jsonify({"recipe": None}), 200


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
