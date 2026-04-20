"""Handlers for the Recipe Builder page.

These endpoints support creating and editing survey recipe JSON files
interactively in the browser, without touching the recipe *runner* logic.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from flask import current_app, jsonify

from src.recipe_validation import validate_recipe
from src.survey_scale_inference import (
    apply_implicit_numeric_level_ranges,
    get_survey_item_map,
)
from src.system_files import filter_system_files

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Keys that are structural metadata in a survey template, not item IDs
_RESERVED_KEYS = {
    "@context",
    "Technical",
    "Study",
    "Metadata",
    "Categories",
    "TaskName",
    "Name",
    "BIDSVersion",
    "Description",
    "URL",
    "License",
    "Authors",
    "Acknowledgements",
    "References",
    "Funding",
    "I18n",
    "Scoring",
    "Normative",
    "Questions",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _global_library_root() -> Path | None:
    """Return the global survey library root (mirrors tools_helpers logic)."""
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


def _library_search_roots(
    dataset_path: str, include_global: bool = False
) -> list[Path]:
    """Return candidate library folders in priority order.

    By default only project-local folders are returned.  Pass
    ``include_global=True`` to also search the official library.
    """
    roots: list[Path] = []
    project = Path(dataset_path)
    for sub in ("code/library/survey", "code/library", "library/survey", "library"):
        candidate = project / sub
        if candidate.is_dir():
            roots.append(candidate)
    if include_global:
        global_root = _global_library_root()
        if global_root:
            roots.append(global_root)
            for sub in ("survey",):
                candidate = global_root / sub
                if candidate.is_dir():
                    roots.append(candidate)
    return roots


def _task_from_template_filename(filename: str) -> str | None:
    """Extract the task name from a survey template filename.

    Handles both::

        task-personality_survey.json  →  personality
        survey-wellbeing.json         →  wellbeing
    """
    stem = Path(filename).stem  # drop .json
    # BIDS style: task-<name>_survey
    m = re.search(r"(?:^|_)task-([^_]+)", stem)
    if m:
        return m.group(1)
    # Legacy style: survey-<name>
    m = re.match(r"survey-(.+)", stem)
    if m:
        return m.group(1)
    return None


def _find_survey_templates(
    dataset_path: str, include_global: bool = False
) -> list[dict]:
    """Return deduplicated survey template JSON files found in library folders.

    Each entry:
      - ``task``      – instrument identifier (e.g. ``wellbeing``)
      - ``label``     – human-readable display name (from template or task)
      - ``file``      – display path (relative where possible)
      - ``source``    – ``"project"`` or ``"official"``
      - ``full_path`` – absolute path (not returned to client)
    """
    found: dict[str, dict] = {}
    dataset_root = Path(dataset_path)
    global_root = _global_library_root()

    for root in _library_search_roots(dataset_path, include_global=include_global):
        for json_file in sorted(root.glob("*.json")):
            cleaned = filter_system_files([json_file.name])
            if not cleaned:
                continue
            task = _task_from_template_filename(json_file.name)
            if not task:
                continue
            if task in found:
                continue

            # Quick check: must look like a survey template (has Technical or Study)
            try:
                with open(json_file, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if "Technical" not in data and "Study" not in data:
                continue

            label = task
            study = data.get("Study") or {}
            if isinstance(study, dict):
                name = study.get("TaskName") or study.get("Name") or ""
                if name:
                    label = name

            try:
                rel = json_file.relative_to(dataset_root)
                display = str(rel)
            except ValueError:
                display = json_file.name

            # Determine source: project-local or official library
            is_global = False
            if global_root:
                try:
                    json_file.relative_to(global_root)
                    is_global = True
                except ValueError:
                    pass

            found[task] = {
                "task": task,
                "label": label,
                "file": display,
                "source": "official" if is_global else "project",
                "full_path": str(json_file),
            }

    return sorted(found.values(), key=lambda d: d["task"])


def _extract_items_from_template(json_path: str) -> list[str]:
    """Return the item/question IDs from a survey template JSON."""
    cleaned = filter_system_files([os.path.basename(json_path)])
    if not cleaned:
        return []
    path = Path(json_path)
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    # Prefer explicit Questions dict (newer PRISM format)
    if "Questions" in data and isinstance(data["Questions"], dict):
        return [
            k
            for k, v in data["Questions"].items()
            if isinstance(v, dict) and not v.get("_exclude", False)
        ]

    # Fallback: top-level keys that look like items
    return [
        k
        for k, v in data.items()
        if k not in _RESERVED_KEYS
        and isinstance(v, dict)
        and "Description" in v
        and not v.get("_exclude", False)
    ]


def _pick_item_description(value) -> str:
    """Return a readable item description from plain or localized values."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("en", "de"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _extract_item_description_metadata_from_template(
    json_path: str,
) -> tuple[dict[str, str], dict[str, dict[str, str]], list[str], str]:
    """Return flattened and language-aware item description metadata.

    Returns a tuple of:
      1) item_descriptions: {itemId: "best available text"}
      2) item_descriptions_i18n: {itemId: {lang: text}}
      3) item_description_languages: sorted list of language keys seen in templates
      4) template_language: Technical.Language hint (if present)
    """
    cleaned = filter_system_files([os.path.basename(json_path)])
    if not cleaned:
        return {}, {}, [], ""
    path = Path(json_path)
    if not path.is_file():
        return {}, {}, [], ""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}, {}, [], ""
    if not isinstance(data, dict):
        return {}, {}, [], ""

    template_language = ""
    technical = data.get("Technical")
    if isinstance(technical, dict):
        maybe_lang = technical.get("Language")
        if isinstance(maybe_lang, str):
            template_language = maybe_lang.strip()

    items_src = get_survey_item_map(data)
    descriptions: dict[str, str] = {}
    descriptions_i18n: dict[str, dict[str, str]] = {}
    languages: set[str] = set()

    for item_id, item_def in items_src.items():
        if item_id in _RESERVED_KEYS or not isinstance(item_def, dict):
            continue
        if item_def.get("_exclude", False):
            continue

        raw_description = item_def.get("Description")
        descriptions[item_id] = _pick_item_description(raw_description)

        per_item_i18n: dict[str, str] = {}
        if isinstance(raw_description, dict):
            for lang_key, lang_text in raw_description.items():
                if not isinstance(lang_key, str) or not isinstance(lang_text, str):
                    continue
                cleaned_key = lang_key.strip()
                cleaned_text = lang_text.strip()
                if not cleaned_key or not cleaned_text:
                    continue
                per_item_i18n[cleaned_key] = cleaned_text
                if cleaned_key.lower() != "default":
                    languages.add(cleaned_key)
        elif isinstance(raw_description, str) and raw_description.strip():
            per_item_i18n["default"] = raw_description.strip()

        if per_item_i18n:
            descriptions_i18n[item_id] = per_item_i18n

    return descriptions, descriptions_i18n, sorted(languages), template_language


def _extract_item_descriptions_from_template(json_path: str) -> dict[str, str]:
    """Return item descriptions keyed by item ID from a survey template JSON."""
    descriptions, _i18n, _languages, _template_language = (
        _extract_item_description_metadata_from_template(json_path)
    )
    return descriptions


def _detect_scale_ranges(json_path: str) -> dict:
    """Return per-variant scale ranges detected from template items.

    The returned dict has:
      - key "" → most common top-level MinValue/MaxValue across all items
      - key "<VariantID>" → most common MinValue/MaxValue for that variant
        (from each item's VariantScales list)

    A missing key means no range could be detected for that variant.
    """
    path = Path(json_path)
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    data = apply_implicit_numeric_level_ranges(data)

    items_src = get_survey_item_map(data)

    # counts[variant_id][(min, max)] = frequency
    from collections import defaultdict

    counts: dict[str, dict[tuple, int]] = defaultdict(dict)

    for v in items_src.values():
        if not isinstance(v, dict):
            continue
        # top-level (default) range
        min_val = v.get("MinValue")
        max_val = v.get("MaxValue")
        if min_val is not None and max_val is not None:
            pair = (min_val, max_val)
            counts[""][pair] = counts[""].get(pair, 0) + 1
        # per-variant ranges
        for vs in v.get("VariantScales") or []:
            if not isinstance(vs, dict):
                continue
            vid = vs.get("VariantID")
            vmin = vs.get("MinValue")
            vmax = vs.get("MaxValue")
            if vid and vmin is not None and vmax is not None:
                pair = (vmin, vmax)
                counts[vid][pair] = counts[vid].get(pair, 0) + 1

    result: dict = {}
    for variant_id, freq in counts.items():
        if freq:
            best = max(freq, key=lambda p: freq[p])
            result[variant_id] = {"min": best[0], "max": best[1]}
    return result


def _extract_item_ranges_from_template(json_path: str) -> dict:
    """Return per-item, per-variant scale ranges from a template.

    Shape: {itemId: {"": {min, max}, variantId: {min, max}, ...}}
    The "" key holds the item's top-level (default) range.
    """
    path = Path(json_path)
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    data = apply_implicit_numeric_level_ranges(data)

    items_src = get_survey_item_map(data)
    result: dict = {}
    for item_id, v in items_src.items():
        if not isinstance(v, dict):
            continue
        item_ranges: dict = {}
        min_val = v.get("MinValue")
        max_val = v.get("MaxValue")
        if min_val is not None and max_val is not None:
            item_ranges[""] = {"min": min_val, "max": max_val}
        for vs in v.get("VariantScales") or []:
            if not isinstance(vs, dict):
                continue
            vid = vs.get("VariantID")
            vmin = vs.get("MinValue")
            vmax = vs.get("MaxValue")
            if vid and vmin is not None and vmax is not None:
                item_ranges[vid] = {"min": vmin, "max": vmax}
        if item_ranges:
            result[item_id] = item_ranges
    return result


def _extract_template_reversed_items(json_path: str) -> list[str]:
    """Return item IDs with template flag Reversed=true."""
    path = Path(json_path)
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    items_src = get_survey_item_map(data)
    reversed_items: list[str] = []
    for item_id, item_def in items_src.items():
        if item_id in _RESERVED_KEYS or not isinstance(item_def, dict):
            continue
        if item_def.get("_exclude", False):
            continue
        if bool(item_def.get("Reversed", False)):
            reversed_items.append(item_id)
    return reversed_items


def _extract_items_missing_ranges_from_template(json_path: str) -> list[str]:
    """Return item IDs missing a usable MinValue/MaxValue after inference."""
    path = Path(json_path)
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    data = apply_implicit_numeric_level_ranges(data)
    items_src = get_survey_item_map(data)
    missing: list[str] = []
    for item_id, item_def in items_src.items():
        if item_id in _RESERVED_KEYS or not isinstance(item_def, dict):
            continue
        if item_def.get("_exclude", False):
            continue

        has_default_range = (
            item_def.get("MinValue") is not None
            and item_def.get("MaxValue") is not None
        )
        has_variant_range = False
        for vs in item_def.get("VariantScales") or []:
            if not isinstance(vs, dict):
                continue
            if vs.get("MinValue") is not None and vs.get("MaxValue") is not None:
                has_variant_range = True
                break

        if not has_default_range and not has_variant_range:
            missing.append(item_id)

    return missing


def _recipe_output_path(dataset_path: str) -> Path:
    """Return the canonical project-local recipe folder (YODA convention)."""
    return Path(dataset_path) / "code" / "recipes" / "survey"


def _task_exists_for_recipe_builder(dataset_path: str, task: str) -> bool:
    """Return True when the task exists in the project or official library."""
    if not dataset_path or not task:
        return False

    templates = _find_survey_templates(dataset_path, include_global=True)
    return any(template["task"] == task for template in templates)


# ---------------------------------------------------------------------------
# Public handlers
# ---------------------------------------------------------------------------


def handle_api_recipe_builder_surveys(dataset_path: str, include_global: bool = False):
    """Return list of survey template JSON files available in the project.

    Pass ``include_global=True`` to also include the official PRISM library.
    """
    if not dataset_path or not os.path.isdir(dataset_path):
        return jsonify({"surveys": []}), 200

    templates = _find_survey_templates(dataset_path, include_global=include_global)
    client = [
        {
            "task": t["task"],
            "label": t["label"],
            "file": t["file"],
            "source": t["source"],
        }
        for t in templates
    ]
    return jsonify({"surveys": client, "include_global": include_global}), 200


def handle_api_recipe_builder_items(
    dataset_path: str, task: str, include_global: bool = False
):
    """Return item IDs for a given survey task, extracted from its template JSON."""
    if not dataset_path or not task:
        return jsonify({"items": []}), 200
    if not os.path.isdir(dataset_path):
        return jsonify({"error": "Project path not found"}), 400

    templates = _find_survey_templates(dataset_path, include_global=include_global)
    match = next((t for t in templates if t["task"] == task), None)
    if match is None:
        return jsonify({"items": []}), 200

    items = _extract_items_from_template(match["full_path"])
    (
        item_descriptions,
        item_descriptions_i18n,
        item_description_languages,
        template_language,
    ) = _extract_item_description_metadata_from_template(match["full_path"])
    scale_ranges = _detect_scale_ranges(match["full_path"])
    item_ranges = _extract_item_ranges_from_template(match["full_path"])
    template_reversed_items = _extract_template_reversed_items(match["full_path"])
    items_missing_ranges = _extract_items_missing_ranges_from_template(
        match["full_path"]
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


def handle_api_recipe_builder_load(dataset_path: str, task: str):
    """Load an existing recipe JSON for the given task (if one exists)."""
    if not dataset_path or not task:
        return jsonify({"recipe": None}), 200

    candidates: list[Path] = [
        Path(dataset_path) / "code" / "recipes" / "survey" / f"recipe-{task}.json",
        Path(dataset_path)
        / "code"
        / "recipes"
        / "survey"
        / f"recipe-{task}_survey.json",
        Path(dataset_path) / "recipe" / "survey" / f"recipe-{task}.json",
        Path(dataset_path) / "recipe" / "survey" / f"recipe-{task}_survey.json",
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
    """Save a recipe JSON to the project's code/recipes/survey folder."""
    dataset_path = (data.get("dataset_path") or "").strip()
    recipe = data.get("recipe")

    if not dataset_path:
        return jsonify({"error": "dataset_path is required"}), 400
    if not os.path.isdir(dataset_path):
        return jsonify({"error": "Project path not found"}), 400
    if not isinstance(recipe, dict):
        return jsonify({"error": "recipe payload is required"}), 400

    task_name = ((recipe.get("Survey") or {}).get("TaskName") or "").strip()
    if not task_name:
        return jsonify({"error": "Recipe must have Survey.TaskName"}), 400

    if not re.fullmatch(r"[a-zA-Z0-9\-]+", task_name):
        return jsonify({"error": "TaskName contains invalid characters"}), 400

    validation_errors = validate_recipe(recipe)
    if validation_errors:
        return (
            jsonify(
                {
                    "error": "Recipe validation failed",
                    "validation_errors": validation_errors,
                }
            ),
            400,
        )

    if not _task_exists_for_recipe_builder(dataset_path, task_name):
        return (
            jsonify(
                {
                    "error": "Survey template not found in the target project or official library"
                }
            ),
            400,
        )

    out_dir = _recipe_output_path(dataset_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"recipe-{task_name}.json"

    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(recipe, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        return jsonify({"error": f"Failed to write recipe: {exc}"}), 500

    return jsonify({"saved": True, "path": str(out_path)}), 200
