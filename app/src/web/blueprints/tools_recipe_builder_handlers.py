"""Handlers for the Recipe Builder page.

These endpoints support creating and editing survey recipe JSON files
interactively in the browser, without touching the recipe *runner* logic.
"""

import json
import os
import re
from pathlib import Path

from flask import current_app, jsonify

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


def _extract_item_descriptions_from_template(json_path: str) -> dict[str, str]:
    """Return item descriptions keyed by item ID from a survey template JSON."""
    cleaned = filter_system_files([os.path.basename(json_path)])
    if not cleaned:
        return {}
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

    items_src = data.get("Questions") if isinstance(data.get("Questions"), dict) else data
    descriptions: dict[str, str] = {}

    for item_id, item_def in items_src.items():
        if item_id in _RESERVED_KEYS or not isinstance(item_def, dict):
            continue
        if item_def.get("_exclude", False):
            continue
        descriptions[item_id] = _pick_item_description(item_def.get("Description"))

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

    _questions = data.get("Questions")
    items_src: dict = _questions if isinstance(_questions, dict) else data

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

    _questions = data.get("Questions")
    items_src: dict = _questions if isinstance(_questions, dict) else data
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


def _recipe_output_path(dataset_path: str) -> Path:
    """Return the canonical project-local recipe folder (YODA convention)."""
    return Path(dataset_path) / "code" / "recipes" / "survey"


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
    item_descriptions = _extract_item_descriptions_from_template(match["full_path"])
    scale_ranges = _detect_scale_ranges(match["full_path"])
    item_ranges = _extract_item_ranges_from_template(match["full_path"])
    return (
        jsonify(
            {
                "items": items,
                "item_descriptions": item_descriptions,
                "scale_ranges": scale_ranges,
                "item_ranges": item_ranges,
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

    out_dir = _recipe_output_path(dataset_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"recipe-{task_name}.json"

    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(recipe, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        return jsonify({"error": f"Failed to write recipe: {exc}"}), 500

    return jsonify({"saved": True, "path": str(out_path)}), 200
