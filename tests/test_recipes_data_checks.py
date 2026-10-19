"""Recipe runs say what looks wrong in the data they score."""

from src.recipes_data_checks import recipe_data_warnings

TEMPLATE = {f"Q{i}": {"Levels": {str(v): str(v) for v in range(0, 5)}} for i in (1, 2, 3)}
RECIPE = {"Scores": [{"Name": "Total", "Method": "sum", "Items": ["Q1", "Q2", "Q3"]}]}


def _files(*rows):
    return [(f"sub-P{n}", {"Q1": a, "Q2": b, "Q3": c}) for n, (a, b, c) in enumerate(rows, 1)]


def _warn(rows, recipe=RECIPE, template=TEMPLATE):
    return recipe_data_warnings("brs", recipe, _files(*rows), template)


def test_clean_data_gives_no_warnings():
    assert _warn([("1", "2", "3"), ("0", "4", "4")]) == []


def test_answers_outside_the_scale_are_listed_with_participant_and_item():
    (text,) = _warn([("9", "2", "3"), ("-1", "2", "3"), ("1", "2", "3")])
    assert "2 answer(s) outside the scale" in text and "sub-P1 Q1=9" in text and "sub-P2 Q1=-1" in text


def test_text_answers_are_reported_as_counted_missing():
    text = _warn([("often", "2", "3"), ("1", "2", "3")])[0]  # the sum then also counts as partial
    assert "not a number" in text and "sub-P1 Q1=often" in text and "missing" in text


def test_a_sum_left_empty_because_of_a_missing_item_is_reported():
    (text,) = _warn([("n/a", "2", "3"), ("1", "2", "3"), ("n/a", "n/a", "n/a")])
    assert "Total" in text and "1 participant(s)" in text and "left empty" in text  # all-missing is just empty


def test_no_empty_sum_warning_when_the_recipe_uses_the_answered_items():
    for extra in ({"Missing": "ignore"}, {"Method": "mean"}):
        recipe = {"Scores": [{**RECIPE["Scores"][0], **extra}]}
        assert _warn([("n/a", "2", "3")], recipe) == [], extra


def test_items_without_levels_are_not_range_checked():
    assert _warn([("99", "2", "3")], template={"Q1": {"Description": "free"}}) == []


def test_decimal_comma_and_whitespace_are_numbers():
    assert _warn([(" 3,0 ", "2", "3")]) == []
