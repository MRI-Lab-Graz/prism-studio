"""Derivative recipe validation (surveys + biometrics).

Recipes live in the repo under:
- recipes/surveys/*.json
- recipes/biometrics/*.json

They are *not* part of a PRISM dataset; therefore they are validated by PRISM tools
before execution.
"""

from __future__ import annotations

import re
from typing import Any

from src.constants import SUPPORTED_MODALITIES

ALLOWED_DERIVED_METHODS = {"max", "min", "mean", "avg", "sum", "map", "formula"}
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


def _unknown_items(items: list[str], known_items_lower: set[str] | None) -> list[str]:
    """Return the subset of ``items`` that aren't in ``known_items_lower``.

    ``known_items_lower`` is ``None`` when no template could be resolved for the
    recipe's task, in which case existence can't be checked and nothing is
    reported. Comparison is case-insensitive to match the case-insensitive
    fallback lookup used when a recipe is actually executed.
    """
    if known_items_lower is None:
        return []
    return sorted({it for it in items if it.lower() not in known_items_lower})


def _validate_score_entries(
    scores: Any,
    *,
    list_label: str,
    errors: list[str],
    prefix: str,
    known_items_lower: set[str] | None = None,
    extra_known_lower: set[str] | None = None,
) -> set[str]:
    """Validate one score list and return its declared output names.

    ``extra_known_lower`` are names that are always resolvable regardless of
    position (e.g. ``Transforms.Derived`` outputs, which are computed before
    any score). In addition, at runtime each score is computed in list order
    and its result is written back into the row before the next score runs
    (see ``_calculate_scores``), so a later score's ``Items`` may legitimately
    reference an *earlier* score's ``Name`` in the same list — that
    availability is tracked here as the list is walked.
    """

    score_names: set[str] = set()
    if not isinstance(scores, list):
        errors.append(prefix + f"{list_label} must be a list")
        return score_names

    available_lower: set[str] = set(extra_known_lower or set())

    for idx, score in enumerate(scores):
        if not isinstance(score, dict):
            errors.append(prefix + f"{list_label}[{idx}] must be an object")
            continue

        name = score.get("Name")
        if not _is_nonempty_str(name):
            errors.append(
                prefix + f"{list_label}[{idx}].Name must be a non-empty string"
            )
            continue

        score_name = str(name).strip()
        if score_name in score_names:
            errors.append(prefix + f"duplicate score Name '{score_name}'")
        score_names.add(score_name)

        combined_known = (
            None if known_items_lower is None else (known_items_lower | available_lower)
        )

        method = str(score.get("Method", "sum")).strip().lower()
        if method not in ALLOWED_SCORE_METHODS:
            errors.append(
                prefix
                + f"{list_label}[{idx}].Method must be one of {sorted(ALLOWED_SCORE_METHODS)}"
            )

        items = _as_list_of_str(score.get("Items"))
        if method == "map":
            source = score.get("Source")
            if not _is_nonempty_str(source):
                errors.append(
                    prefix
                    + f"{list_label}[{idx}] uses Method='map' but has no non-empty Source"
                )
            else:
                unknown_source = _unknown_items([str(source).strip()], combined_known)
                if unknown_source:
                    errors.append(
                        prefix
                        + f"{list_label}[{idx}].Source '{unknown_source[0]}' is not an item "
                        f"in the matched template"
                    )
            mapping = score.get("Mapping")
            if not isinstance(mapping, dict) or not mapping:
                errors.append(
                    prefix
                    + f"{list_label}[{idx}] uses Method='map' but has no non-empty Mapping object"
                )
        elif not items:
            errors.append(
                prefix
                + f"{list_label}[{idx}].Items must be a non-empty list of strings"
            )

        if items:
            unknown = _unknown_items(items, combined_known)
            if unknown:
                errors.append(
                    prefix
                    + f"{list_label}[{idx}].Items references item(s) not found in the "
                    f"matched template: {unknown}"
                )

        missing = str(score.get("Missing", "ignore")).strip().lower()
        if missing not in ALLOWED_MISSING:
            errors.append(
                prefix
                + f"{list_label}[{idx}].Missing must be one of {sorted(ALLOWED_MISSING)}"
            )

        min_valid = score.get("MinValid")
        if min_valid is not None:
            if isinstance(min_valid, bool) or not isinstance(min_valid, int):
                errors.append(
                    prefix + f"{list_label}[{idx}].MinValid must be an integer >= 1"
                )
            elif min_valid < 1:
                errors.append(prefix + f"{list_label}[{idx}].MinValid must be >= 1")
            elif not items:
                errors.append(
                    prefix
                    + f"{list_label}[{idx}].MinValid requires a non-empty Items list"
                )
            elif min_valid > len(items):
                errors.append(
                    prefix
                    + f"{list_label}[{idx}].MinValid ({min_valid}) cannot exceed number of Items ({len(items)})"
                )

        if method == "formula":
            formula = score.get("Formula")
            if not _is_nonempty_str(formula):
                errors.append(
                    prefix
                    + f"{list_label}[{idx}] uses Method='formula' but has no non-empty Formula"
                )
            else:
                placeholders = [
                    m.group(1).strip() for m in _PLACEHOLDER_RE.finditer(str(formula))
                ]
                if not placeholders:
                    errors.append(
                        prefix + f"{list_label}[{idx}].Formula has no {{placeholders}}"
                    )
                missing_refs = sorted({p for p in placeholders if p not in items})
                if missing_refs:
                    errors.append(
                        prefix
                        + f"{list_label}[{idx}].Formula references {missing_refs} but they are not listed in Items (they would not be substituted)"
                    )

        # Available to *later* entries in this same list only (matches the
        # sequential, row-mutating order _calculate_scores runs in).
        available_lower.add(score_name.lower())

    return score_names


def validate_recipe(
    recipe: dict[str, Any],
    *,
    recipe_id: str | None = None,
    known_items: set[str] | None = None,
) -> list[str]:
    """Return a list of human-readable validation errors for a recipe.

    ``known_items`` is the set of item IDs found in the survey/biometrics
    template matched to this recipe's task. When provided, every item ID
    referenced by ``Scores``, ``VersionedScores``, ``Transforms.Derived`` and
    ``Transforms.Invert`` is checked against it, so a typo'd or renamed item ID
    is reported as a validation error instead of silently resolving to no
    value at scoring time. Pass ``None`` (the default) to skip this check when
    the matched template can't be resolved.
    """

    errors: list[str] = []
    prefix = f"recipe '{recipe_id}': " if recipe_id else ""

    if not isinstance(recipe, dict):
        return [prefix + "recipe must be a JSON object"]

    known_items_lower = (
        {str(i).strip().lower() for i in known_items} if known_items is not None else None
    )

    kind = str(recipe.get("Kind", "")).strip().lower()
    if kind not in SUPPORTED_MODALITIES:
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
            errors.append(
                prefix + "Biometrics must be an object when Kind='biometrics'"
            )
        else:
            if not _is_nonempty_str(biom.get("BiometricName")):
                errors.append(
                    prefix + "Biometrics.BiometricName must be a non-empty string"
                )

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
                errors.append(
                    prefix
                    + "Transforms.Invert.Items must be a non-empty list of strings"
                )
            else:
                unknown = _unknown_items(inv_items, known_items_lower)
                if unknown:
                    errors.append(
                        prefix
                        + f"Transforms.Invert.Items references item(s) not found in the "
                        f"matched template: {unknown}"
                    )
            scale = invert.get("Scale")
            if not isinstance(scale, dict):
                errors.append(
                    prefix + "Transforms.Invert.Scale must be an object with min/max"
                )
            else:
                if scale.get("min") is None or scale.get("max") is None:
                    errors.append(
                        prefix + "Transforms.Invert.Scale must include min and max"
                    )
            # ItemScales is optional: per-item override of Scale
            item_scales = invert.get("ItemScales")
            if item_scales is not None:
                if not isinstance(item_scales, dict):
                    errors.append(
                        prefix + "Transforms.Invert.ItemScales must be an object"
                    )
                else:
                    for iid, isc in item_scales.items():
                        if (
                            not isinstance(isc, dict)
                            or isc.get("min") is None
                            or isc.get("max") is None
                        ):
                            errors.append(
                                prefix
                                + f"Transforms.Invert.ItemScales.{iid} must have min and max"
                            )
                    unknown = _unknown_items(list(item_scales.keys()), known_items_lower)
                    if unknown:
                        errors.append(
                            prefix
                            + f"Transforms.Invert.ItemScales references item(s) not found in "
                            f"the matched template: {unknown}"
                        )

    # Derived
    derived_cfg = (transforms or {}).get("Derived")
    derived_names: set[str] = set()
    # Names available to *later* Derived entries only: _calculate_derived_variables
    # runs the list in order and writes each result back into the row before the
    # next entry runs, so a later Derived can legitimately reference an earlier one.
    available_derived_lower: set[str] = set()
    if derived_cfg is not None:
        if not isinstance(derived_cfg, list):
            errors.append(prefix + "Transforms.Derived must be a list")
        else:
            for idx, d in enumerate(derived_cfg):
                if not isinstance(d, dict):
                    errors.append(
                        prefix + f"Transforms.Derived[{idx}] must be an object"
                    )
                    continue
                name = d.get("Name")
                if not _is_nonempty_str(name):
                    errors.append(
                        prefix
                        + f"Transforms.Derived[{idx}].Name must be a non-empty string"
                    )
                else:
                    n = str(name).strip()
                    if n in derived_names:
                        errors.append(prefix + f"duplicate derived Name '{n}'")
                    derived_names.add(n)

                method = str(d.get("Method", "max")).strip().lower()
                if method not in ALLOWED_DERIVED_METHODS:
                    errors.append(
                        prefix
                        + f"Transforms.Derived[{idx}].Method must be one of {sorted(ALLOWED_DERIVED_METHODS)}"
                    )

                items = _as_list_of_str(d.get("Items"))
                combined_known = (
                    None
                    if known_items_lower is None
                    else (known_items_lower | available_derived_lower)
                )

                if items:
                    unknown = _unknown_items(items, combined_known)
                    if unknown:
                        errors.append(
                            prefix
                            + f"Transforms.Derived[{idx}].Items references item(s) not found "
                            f"in the matched template: {unknown}"
                        )

                if method == "map":
                    # Allow either explicit Source or implicit first Items entry.
                    source = d.get("Source")
                    if not _is_nonempty_str(source) and not items:
                        errors.append(
                            prefix
                            + f"Transforms.Derived[{idx}] uses Method='map' but has no non-empty Source and no Items"
                        )
                    elif _is_nonempty_str(source):
                        unknown = _unknown_items([str(source).strip()], combined_known)
                        if unknown:
                            errors.append(
                                prefix
                                + f"Transforms.Derived[{idx}].Source '{str(source).strip()}' "
                                f"is not an item in the matched template"
                            )
                    mapping = d.get("Mapping")
                    if not isinstance(mapping, dict) or not mapping:
                        errors.append(
                            prefix
                            + f"Transforms.Derived[{idx}] uses Method='map' but has no non-empty Mapping object"
                        )
                elif method == "formula":
                    formula = d.get("Formula")
                    if not _is_nonempty_str(formula):
                        errors.append(
                            prefix
                            + f"Transforms.Derived[{idx}] uses Method='formula' but has no non-empty Formula"
                        )
                    if not items:
                        errors.append(
                            prefix
                            + f"Transforms.Derived[{idx}].Items must be a non-empty list of strings"
                        )
                    else:
                        placeholders = [
                            m.group(1).strip()
                            for m in _PLACEHOLDER_RE.finditer(str(formula or ""))
                        ]
                        if placeholders:
                            missing_refs = sorted(
                                {p for p in placeholders if p not in items}
                            )
                            if missing_refs:
                                errors.append(
                                    prefix
                                    + f"Transforms.Derived[{idx}].Formula references {missing_refs} but they are not listed in Items (they would not be substituted)"
                                )
                else:
                    if not items:
                        errors.append(
                            prefix
                            + f"Transforms.Derived[{idx}].Items must be a non-empty list of strings"
                        )

                if _is_nonempty_str(name):
                    available_derived_lower.add(str(name).strip().lower())

    # Scores
    score_names_for_collision: set[str] = set()
    scores = recipe.get("Scores")
    versioned_scores = recipe.get("VersionedScores")
    if scores is None and versioned_scores is None:
        errors.append(
            prefix + "Scores is missing (recipe will produce no output columns)"
        )
    elif scores is not None:
        score_names_for_collision.update(
            _validate_score_entries(
                scores,
                list_label="Scores",
                errors=errors,
                prefix=prefix,
                known_items_lower=known_items_lower,
                extra_known_lower=available_derived_lower,
            )
        )

    if versioned_scores is not None:
        if not isinstance(versioned_scores, dict):
            errors.append(prefix + "VersionedScores must be an object")
        else:
            for version_key, version_scores in versioned_scores.items():
                if not _is_nonempty_str(version_key):
                    errors.append(
                        prefix + "VersionedScores keys must be non-empty strings"
                    )
                    continue
                score_names_for_collision.update(
                    _validate_score_entries(
                        version_scores,
                        list_label=f"VersionedScores.{str(version_key).strip()}",
                        errors=errors,
                        prefix=prefix,
                        known_items_lower=known_items_lower,
                        extra_known_lower=available_derived_lower,
                    )
                )

    # Prevent collisions between Derived and Scores names
    collisions = sorted(derived_names.intersection(score_names_for_collision))
    if collisions:
        errors.append(
            prefix + f"Name collision between Derived and Scores: {collisions}"
        )

    return errors
