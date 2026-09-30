"""Method 'irv': one person's response variability (SD of raw answers)."""

from src.recipe_validation import validate_recipe
from src.recipes_formula_engine import _calculate_scores

IRV = {"Name": "IRV", "Method": "irv", "Items": ["A", "B", "C", "D"]}


def _irv(row, invert=frozenset(), score=IRV):
    return _calculate_scores([score], dict(row), set(invert), 1, 5)["IRV"]


def test_same_answer_everywhere_is_zero():
    assert _irv({"A": "3", "B": "3", "C": "3", "D": "3"}) == "0"


def test_varied_answers_give_the_sample_sd():
    # sample SD of 1,2,3,4 = 1.2909944...
    assert abs(float(_irv({"A": "1", "B": "2", "C": "3", "D": "4"})) - 1.2909944) < 1e-5


def test_reverse_coding_does_not_change_it():
    row = {"A": "5", "B": "5", "C": "5", "D": "5"}
    assert _irv(row, invert={"B", "D"}) == "0"


def test_fewer_than_two_answers_is_empty():
    assert _irv({"A": "3", "B": "n/a", "C": "", "D": "n/a"}) == "n/a"


def test_min_valid_is_respected():
    score = {**IRV, "MinValid": 3}
    assert _irv({"A": "1", "B": "2", "C": "n/a", "D": "n/a"}, score=score) == "n/a"


def test_recipe_validation_accepts_irv():
    recipe = {
        "RecipeVersion": "1.0.0",
        "Kind": "survey",
        "Survey": {"Name": "x", "TaskName": "x"},
        "Scores": [IRV],
    }
    assert not [e for e in validate_recipe(recipe) if "Method" in e]
