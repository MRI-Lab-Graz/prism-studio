"""max/min are Transforms.Derived methods only; as a score Method they must say so."""

import pytest

from src.recipe_validation import validate_recipe


def _recipe(**sections):
    recipe = {"Kind": "survey", "RecipeVersion": "1.0", "Survey": {"TaskName": "demo"}}
    recipe.update(sections)
    return recipe


@pytest.mark.parametrize("method", ["max", "min"])
def test_max_min_score_is_rejected_with_hint(method):
    score = {"Name": "s", "Method": method, "Items": ["a", "b"]}
    errors = [e for e in validate_recipe(_recipe(Scores=[score])) if "Method" in e]
    assert len(errors) == 1
    assert "Transforms.Derived" in errors[0]


def test_max_derived_is_still_valid():
    derived = {"Name": "s", "Method": "max", "Items": ["a", "b"]}
    errors = validate_recipe(
        _recipe(Scores=[{"Name": "t", "Method": "sum", "Items": ["a"]}], Transforms={"Derived": [derived]})
    )
    assert not [e for e in errors if "Method" in e]
