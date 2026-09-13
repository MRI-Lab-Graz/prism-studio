"""Tests for src.recipe_validation.validate_recipe_warnings.

A `Method: sum`/`mean` score with `Missing: "ignore"` (the default) and no
`MinValid` sums/averages whatever items were answered, with no signal that
a participant who answered 1-of-10 items produced a score indistinguishable
from one who answered all 10 -- see recipes_formula_engine.py::
_calculate_scores. Changing that scoring math would silently change every
previously-computed score for existing recipes, so this is a non-blocking
warning surfaced to the recipe author (Recipe Builder save response),
not a validation error and not a change to how scores are computed.
"""

from __future__ import annotations

from src.recipe_validation import validate_recipe_warnings


def _recipe(**overrides):
    recipe = {
        "Kind": "survey",
        "RecipeVersion": "1.0",
        "Survey": {"TaskName": "demo"},
        "Scores": [
            {"Name": "total", "Method": "sum", "Items": ["q1", "q2", "q3"]},
        ],
    }
    recipe.update(overrides)
    return recipe


def test_warns_on_sum_without_min_valid_and_default_missing_policy():
    warnings = validate_recipe_warnings(_recipe())
    assert len(warnings) == 1
    assert "total" in warnings[0]
    assert "MinValid" in warnings[0]


def test_no_warning_when_min_valid_is_set():
    recipe = _recipe(
        Scores=[
            {"Name": "total", "Method": "sum", "Items": ["q1", "q2", "q3"], "MinValid": 2},
        ]
    )
    assert validate_recipe_warnings(recipe) == []


def test_no_warning_when_missing_requires_all_items():
    recipe = _recipe(
        Scores=[
            {
                "Name": "total",
                "Method": "sum",
                "Items": ["q1", "q2", "q3"],
                "Missing": "require_all",
            },
        ]
    )
    assert validate_recipe_warnings(recipe) == []


def test_no_warning_for_single_item_score():
    recipe = _recipe(
        Scores=[{"Name": "single", "Method": "sum", "Items": ["q1"]}]
    )
    assert validate_recipe_warnings(recipe) == []


def test_no_warning_for_formula_or_map_methods():
    recipe = _recipe(
        Scores=[
            {"Name": "f", "Method": "formula", "Items": ["q1", "q2"], "Formula": "{q1}+{q2}"},
        ]
    )
    assert validate_recipe_warnings(recipe) == []


def test_warns_for_versioned_scores_too():
    recipe = _recipe(
        Scores=[],
        VersionedScores={
            "v1": [{"Name": "total_v1", "Method": "mean", "Items": ["q1", "q2"]}],
        },
    )
    warnings = validate_recipe_warnings(recipe)
    assert len(warnings) == 1
    assert "total_v1" in warnings[0]
