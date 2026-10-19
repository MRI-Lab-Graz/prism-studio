"""A sum is empty when any item is missing; a mean uses the answered items (unless the recipe says otherwise)."""

import pytest

from src.recipes_formula_engine import _calculate_scores, effective_missing


def _score(method="sum", **extra):
    return {"Name": "S", "Method": method, "Items": ["A", "B", "C"], **extra}


def _run(score, row):
    return _calculate_scores([score], dict(row), set(), None, None)["S"]


COMPLETE = {"A": "1", "B": "2", "C": "3"}
PARTIAL = {"A": "n/a", "B": "2", "C": "3"}


def test_complete_answers_sum_normally():
    assert _run(_score(), COMPLETE) == "6"


def test_a_sum_with_a_missing_item_is_empty_by_default():
    assert _run(_score(), PARTIAL) == "n/a"
    assert _run(_score(), {"A": "", "B": "", "C": ""}) == "n/a"


def test_a_recipe_can_opt_into_summing_the_answered_items():
    assert _run(_score(Missing="ignore"), PARTIAL) == "5"


def test_min_valid_still_applies_when_the_sum_ignores_missing_items():
    assert _run(_score(Missing="ignore", MinValid=3), PARTIAL) == "n/a"
    assert _run(_score(Missing="ignore", MinValid=2), PARTIAL) == "5"


def test_a_mean_uses_the_answered_items_by_default():
    assert _run(_score("mean"), PARTIAL) == "2.5"
    assert _run(_score("mean", Missing="require_all"), PARTIAL) == "n/a"


@pytest.mark.parametrize("method,given,expected", [
    ("sum", None, "require_all"), ("sum", "ignore", "ignore"), ("sum", "Strict", "require_all"),
    ("mean", None, "ignore"), ("mean", "all", "require_all"), ("irv", None, "ignore"),
])
def test_effective_missing(method, given, expected):
    score = {"Method": method, **({"Missing": given} if given else {})}
    assert effective_missing(score) == expected
