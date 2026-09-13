"""Tests for reverse-scoring (Transforms.Invert) in recipes_formula_engine.

Two bugs found during a Recipe Builder assessment:

1. Invert.Items matching was case-sensitive while item lookup and recipe
   validation are both case-insensitive, so a recipe like
   ``Invert.Items: ["wb01"]`` against a column named ``WB01`` validated
   clean and scored, but silently skipped the reversal.
2. A response value outside the declared Invert.Scale range (a data-entry
   error, e.g. "9" on a 1-5 scale) was extrapolated with
   ``max + min - value`` into a nonsensical, out-of-range result instead
   of being treated as unusable.
"""

from __future__ import annotations

from src.recipes_formula_engine import _calculate_scores, _get_item_value


def test_invert_items_matches_case_insensitively():
    row = {"WB01": "5"}
    out = _calculate_scores(
        [{"Name": "S", "Method": "sum", "Items": ["WB01"]}],
        row,
        invert_items={"wb01"},
        invert_min=1,
        invert_max=5,
    )
    # 1 + 5 - 5 = 1
    assert out["S"] == "1"


def test_invert_item_scales_matches_case_insensitively():
    row = {"WB01": "5"}
    out = _calculate_scores(
        [{"Name": "S", "Method": "sum", "Items": ["WB01"]}],
        row,
        invert_items={"wb01"},
        invert_min=1,
        invert_max=7,
        item_scales={"wb01": {"min": 1, "max": 5}},
    )
    assert out["S"] == "1"


def test_out_of_range_value_is_treated_as_missing_when_inverted():
    # Declared scale is 1-5; a "9" is a data-entry error, not a valid
    # response -- must not be extrapolated to a negative/out-of-range score.
    value = _get_item_value("A", {"A": "9"}, invert_items={"A"}, invert_min=1, invert_max=5)
    assert value is None


def test_in_range_value_still_inverts_normally():
    value = _get_item_value("A", {"A": "5"}, invert_items={"A"}, invert_min=1, invert_max=5)
    assert value == 1.0


def test_boundary_values_are_in_range():
    assert _get_item_value("A", {"A": "1"}, invert_items={"A"}, invert_min=1, invert_max=5) == 5.0
    assert _get_item_value("A", {"A": "5"}, invert_items={"A"}, invert_min=1, invert_max=5) == 1.0


def test_out_of_range_item_drops_score_below_min_valid():
    row = {"A": "3", "B": "9"}  # B is out of the declared 1-5 scale
    out = _calculate_scores(
        [{"Name": "S", "Method": "sum", "Items": ["A", "B"], "MinValid": 2}],
        row,
        invert_items={"B"},
        invert_min=1,
        invert_max=5,
    )
    assert out["S"] == "n/a"
