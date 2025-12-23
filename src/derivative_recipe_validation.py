"""Derivative recipe validation (surveys + biometrics).

Recipes live in the repo under:
- derivatives/surveys/*.json
- derivatives/biometrics/*.json

They are *not* part of a PRISM dataset; therefore they are validated by PRISM tools
before execution.
"""

from __future__ import annotations

import re
from typing import Any


ALLOWED_DERIVED_METHODS = {"max", "min", "mean", "avg", "sum"}
ALLOWED_SCORE_METHODS = {"sum", "mean", "formula", "map"}
ALLOWED_MISSING = {"ignore", "require_all", "all", "strict"}


_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _as_list_of_str(x: Any) -> list[str]:
    if not isinstance(x, list):
        return []
    out: list[str] = []
    for v in x:
        if _is_nonempty_str(v):
            out.append(v.strip())
    return out


def validate_derivative_recipe(recipe: dict[str, Any], *, recipe_id: str | None = None) -> list[str]:
    """Return a list of human-readable validation errors for a recipe."""

    errors: list[str] = []
    prefix = f"recipe '{recipe_id}': " if recipe_id else ""

    if not isinstance(recipe, dict):
        return [prefix + "recipe must be a JSON object"]

    kind = str(recipe.get("Kind", "")).strip().lower()
    if kind not in {"survey", "biometrics"}:
        errors.append(prefix + "Kind must be 'survey' or 'biometrics'")

    if not _is_nonempty_str(recipe.get("RecipeVersion")):
        errors.append(prefix + "RecipeVersion must be a non-empty string")

    if kind == "survey":
        survey = recipe.get("Survey")
        if not isinstance(survey, dict):
            errors.append(prefix + "Survey must be an object when Kind='survey'")
        else:
            if not _is_nonempty_str(survey.get("TaskName")):
                errors.append(prefix + "Survey.TaskName must be a non-empty string")
    elif kind == "biometrics":
        biom = recipe.get("Biometrics")
        if not isinstance(biom, dict):
            errors.append(prefix + "Biometrics must be an object when Kind='biometrics'")
        else:
            if not _is_nonempty_str(biom.get("BiometricName")):
                errors.append(prefix + "Biometrics.BiometricName must be a non-empty string")

    transforms = recipe.get("Transforms") or {}
    if transforms is not None and not isinstance(transforms, dict):
        errors.append(prefix + "Transforms must be an object")
        transforms = {}

    # Invert
    invert = (transforms or {}).get("Invert")
    if invert is not None:
        if not isinstance(invert, dict):
            errors.append(prefix + "Transforms.Invert must be an object")
        else:
            inv_items = _as_list_of_str(invert.get("Items"))
            if not inv_items:
                errors.append(prefix + "Transforms.Invert.Items must be a non-empty list of strings")
            scale = invert.get("Scale")
            if not isinstance(scale, dict):
                errors.append(prefix + "Transforms.Invert.Scale must be an object with min/max")
            else:
                if scale.get("min") is None or scale.get("max") is None:
                    errors.append(prefix + "Transforms.Invert.Scale must include min and max")

    # Derived
    derived_cfg = (transforms or {}).get("Derived")
    derived_names: set[str] = set()
    if derived_cfg is not None:
        if not isinstance(derived_cfg, list):
            errors.append(prefix + "Transforms.Derived must be a list")
        else:
            for idx, d in enumerate(derived_cfg):
                if not isinstance(d, dict):
                    errors.append(prefix + f"Transforms.Derived[{idx}] must be an object")
                    continue
                name = d.get("Name")
                if not _is_nonempty_str(name):
                    errors.append(prefix + f"Transforms.Derived[{idx}].Name must be a non-empty string")
                else:
                    n = str(name).strip()
                    if n in derived_names:
                        errors.append(prefix + f"duplicate derived Name '{n}'")
                    derived_names.add(n)

                method = str(d.get("Method", "max")).strip().lower()
                if method not in ALLOWED_DERIVED_METHODS:
                    errors.append(prefix + f"Transforms.Derived[{idx}].Method must be one of {sorted(ALLOWED_DERIVED_METHODS)}")

                items = _as_list_of_str(d.get("Items"))
                if not items:
                    errors.append(prefix + f"Transforms.Derived[{idx}].Items must be a non-empty list of strings")

    # Scores
    scores = recipe.get("Scores")
    score_names: set[str] = set()
    if scores is None:
        # allowed, but produces no output; keep as a warning-level error message
        errors.append(prefix + "Scores is missing (recipe will produce no output columns)")
    elif not isinstance(scores, list):
        errors.append(prefix + "Scores must be a list")
    else:
        for idx, s in enumerate(scores):
            if not isinstance(s, dict):
                errors.append(prefix + f"Scores[{idx}] must be an object")
                continue

            name = s.get("Name")
            if not _is_nonempty_str(name):
                errors.append(prefix + f"Scores[{idx}].Name must be a non-empty string")
                continue

            n = str(name).strip()
            if n in score_names:
                errors.append(prefix + f"duplicate score Name '{n}'")
            score_names.add(n)

            method = str(s.get("Method", "sum")).strip().lower()
            if method not in ALLOWED_SCORE_METHODS:
                errors.append(prefix + f"Scores[{idx}].Method must be one of {sorted(ALLOWED_SCORE_METHODS)}")

            items = _as_list_of_str(s.get("Items"))
            if method == "map":
                source = s.get("Source")
                if not _is_nonempty_str(source):
                    errors.append(prefix + f"Scores[{idx}] uses Method='map' but has no non-empty Source")
                mapping = s.get("Mapping")
                if not isinstance(mapping, dict) or not mapping:
                    errors.append(prefix + f"Scores[{idx}] uses Method='map' but has no non-empty Mapping object")
            elif not items:
                errors.append(prefix + f"Scores[{idx}].Items must be a non-empty list of strings")

            missing = str(s.get("Missing", "ignore")).strip().lower()
            if missing not in ALLOWED_MISSING:
                errors.append(prefix + f"Scores[{idx}].Missing must be one of {sorted(ALLOWED_MISSING)}")

            if method == "formula":
                formula = s.get("Formula")
                if not _is_nonempty_str(formula):
                    errors.append(prefix + f"Scores[{idx}] uses Method='formula' but has no non-empty Formula")
                else:
                    placeholders = [m.group(1).strip() for m in _PLACEHOLDER_RE.finditer(str(formula))]
                    if not placeholders:
                        errors.append(prefix + f"Scores[{idx}].Formula has no {{placeholders}}")
                    # Important: current eval implementation only replaces placeholders for ids present in Items
                    missing_refs = sorted({p for p in placeholders if p not in items})
                    if missing_refs:
                        errors.append(
                            prefix
                            + f"Scores[{idx}].Formula references {missing_refs} but they are not listed in Items (they would not be substituted)"
                        )

    # Prevent collisions between Derived and Scores names
    collisions = sorted(derived_names.intersection(score_names))
    if collisions:
        errors.append(prefix + f"Name collision between Derived and Scores: {collisions}")

    return errors
