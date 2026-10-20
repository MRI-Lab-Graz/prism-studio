"""Scoring recipes and software versions of a project, for the methods text."""

from __future__ import annotations

import json
from pathlib import Path

from src import __version__
from src.modality_versions import read_pins

# ponytail: eligibility_flags omitted - check_eligibility returns messages, not a participant count
RECIPE_GLOB = "code/recipes/*/recipe-*.json"


def processing_summary(project_path: Path) -> dict:
    """``{"recipes": [{"task", "scores"}], "software": {"prism_version", "modality_schemas"}}``."""
    project_path = Path(project_path)
    recipes = []
    for path in sorted(project_path.glob(RECIPE_GLOB)):
        try:
            recipe = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        survey = recipe.get("Survey") if isinstance(recipe, dict) else None
        task = (survey or {}).get("TaskName") if isinstance(survey, dict) else None
        scores = [
            str(s["Name"]) for s in (recipe.get("Scores") or []) if isinstance(s, dict) and s.get("Name")
        ]
        if task and scores:
            recipes.append({"task": str(task), "scores": scores})
    return {
        "recipes": recipes,
        "software": {"prism_version": __version__, "modality_schemas": read_pins(project_path)[0]},
    }
