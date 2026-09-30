"""A missing item must not silently count as 0 in a formula score."""

from src.recipes_formula_engine import _calculate_scores

SUM_FORMULA = {"Name": "x", "Method": "formula", "Formula": "{A}+{B}", "Items": ["A", "B"]}


def _score(score, row):
    return _calculate_scores([score], dict(row), set(), None, None)


def test_formula_with_a_missing_item_leaves_the_score_empty():
    assert _score(SUM_FORMULA, {"A": "2", "B": "n/a"}) == {"x": "n/a"}
    assert _score(SUM_FORMULA, {"A": "2", "B": ""}) == {"x": "n/a"}


def test_formula_with_every_item_missing_is_empty_not_zero():
    assert _score(SUM_FORMULA, {"A": "n/a", "B": "n/a"}) == {"x": "n/a"}


def test_formula_with_every_item_answered_still_scores():
    assert _score(SUM_FORMULA, {"A": "2", "B": "3"}) == {"x": "5"}


def test_a_real_zero_is_still_a_zero():
    assert _score(SUM_FORMULA, {"A": "0", "B": "0"}) == {"x": "0"}


def test_formulas_with_text_items_still_work_when_answered():
    conditional = {
        "Name": "y",
        "Method": "formula",
        "Formula": "{q1} if ({sex} == 'M') else {q2}",
        "Items": ["q1", "sex", "q2"],
    }

    assert _score(conditional, {"q1": "4", "sex": "M", "q2": "9"}) == {"y": "4"}
    assert _score(conditional, {"q1": "4", "sex": "F", "q2": "9"}) == {"y": "9"}
