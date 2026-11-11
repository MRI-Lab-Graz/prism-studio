import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "app/schemas/stable/recipe.survey.schema.json").read_text())
V = Draft7Validator(SCHEMA)


def _recipe(**score_extra):
    recipe = json.loads((ROOT / "official/recipe/survey/recipe-phq9.json").read_text())
    # the official file says "1.0.0", the schema wants "1.0": a separate, older mismatch
    recipe["RecipeVersion"] = "1.0"
    recipe["Scores"] = [{**recipe["Scores"][0], **score_extra}]
    return recipe


def test_base_recipe_validates():
    assert not list(V.iter_errors(_recipe()))


def test_higher_and_lower_means_are_accepted():
    assert not list(
        V.iter_errors(
            _recipe(
                HigherMeans="more depressive symptoms",
                LowerMeans="fewer depressive symptoms",
            )
        )
    )


def test_lower_means_alone_is_accepted():
    assert not list(V.iter_errors(_recipe(LowerMeans="more introverted")))


@pytest.mark.parametrize("key", ["HigherMeans", "LowerMeans"])
@pytest.mark.parametrize("value", ["", 3, ["more"], None])
def test_means_refuses_empty_or_non_text(key, value):
    assert list(V.iter_errors(_recipe(**{key: value})))
