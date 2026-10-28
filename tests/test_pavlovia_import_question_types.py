"""Question types of a real SurveyJS file that the Pavlovia import used to get wrong: rating ranges,
localized texts, matrices, multiple text, checkbox/other/none, and the types that are no response
(html) or cannot be represented (they are reported as import notes, never dropped silently)."""

from __future__ import annotations

import pytest

from src.converters.pavlovia_import import pavlovia_questionnaire


def _import(*elements, language="de", **survey):
    template, notes = pavlovia_questionnaire(
        {"pages": [{"name": "p", "elements": list(elements)}], **survey}, "p1", language=language
    )
    return template, notes


def _items(template):
    return {k: v for k, v in template.items() if k not in ("Technical", "Study", "Metadata")}


@pytest.mark.parametrize(
    "scale, expected",
    [
        ({"rateMin": 0, "rateMax": 4}, ["0", "1", "2", "3", "4"]),
        ({"rateMin": 0, "rateMax": 10, "rateStep": 5}, ["0", "5", "10"]),
        ({"rateCount": 3}, ["1", "2", "3"]),
        ({"rateMin": 2, "rateCount": 3}, ["2", "3", "4"]),
        ({}, ["1", "2", "3", "4", "5"]),
    ],
)
def test_rating_levels_follow_min_max_step_and_count(scale, expected):
    template, _notes = _import({"type": "rating", "name": "r", "title": "R", **scale})
    assert list(template["r"]["Levels"]) == expected


def test_localized_texts_are_taken_in_the_chosen_language_and_the_others_reported():
    template, notes = _import(
        {"type": "radiogroup", "name": "q", "title": {"default": "Eng", "de": "Deutsch", "fr": "Allemand"},
         "choices": [{"value": "a", "text": {"default": "Yes", "de": "Ja"}}]},
    )
    assert template["q"]["Description"] == {"de": "Deutsch"}
    assert template["q"]["Levels"] == {"a": {"de": "Ja"}}
    assert any("other languages (fr)" in n for n in notes)


def test_localized_text_without_a_chosen_language_uses_the_default_text():
    template, _notes = _import({"type": "comment", "name": "q", "title": {"default": "Eng", "de": "Deutsch"}}, language=None)
    assert template["q"]["Description"] == "Eng"


def test_matrix_rows_become_items_sharing_the_columns_as_levels():
    template, _notes = _import(
        {"type": "matrix", "name": "mx", "title": "Matrix", "columns": ["1", {"value": "2", "text": "two"}],
         "rows": ["r1", {"value": "r2", "text": "Row two"}]}
    )
    assert "mx" not in template
    assert template["mx_r1"]["Levels"] == {"1": {"de": "1"}, "2": {"de": "two"}}
    assert template["mx_r2"]["Description"] == {"de": "Matrix - Row two"}
    assert template["Study"]["ItemCount"] == 2


def test_multipletext_items_become_text_items():
    template, _notes = _import(
        {"type": "multipletext", "name": "mt", "title": "MT", "items": [{"name": "a", "title": "A"}, {"name": "b"}]}
    )
    assert template["mt_a"]["Description"] == {"de": "MT - A"}
    assert template["mt_b"]["DataType"] == "string"


def test_checkbox_stays_one_item_and_the_multiple_selection_is_reported():
    template, notes = _import({"type": "checkbox", "name": "cb", "title": "Pick", "choices": ["a", "b"]})
    assert list(template["cb"]["Levels"]) == ["a", "b"]
    assert any("cb" in n and "several" in n for n in notes)


def test_other_and_none_options_are_levels_and_other_has_a_comment_item():
    template, _notes = _import(
        {"type": "radiogroup", "name": "q", "title": "Q", "choices": ["a"], "showOtherItem": True, "showNoneItem": True}
    )
    assert list(template["q"]["Levels"]) == ["a", "other", "none"]
    assert template["q-Comment"]["DataType"] == "string"


def test_html_is_not_a_response_and_is_skipped_with_a_note():
    template, notes = _import({"type": "html", "name": "h", "html": "<b>hi</b>"}, {"type": "comment", "name": "c", "title": "C"})
    assert "h" not in template and template["Study"]["ItemCount"] == 1
    assert any("'h'" in n and "html" in n for n in notes)


@pytest.mark.parametrize(
    "element",
    [
        {"type": "expression", "name": "x", "title": "X", "expression": "{a} + 1"},
        {"type": "ranking", "name": "x", "title": "X", "choices": ["u", "v"]},
        {"type": "file", "name": "x", "title": "X"},
        {"type": "matrixdropdown", "name": "x", "title": "X", "columns": [{"name": "c"}], "rows": ["r"]},
        {"type": "radiogroup", "name": "x", "title": "X", "choicesFromQuestion": "other"},
    ],
)
def test_what_cannot_be_represented_is_reported(element):
    _template, notes = _import(element)
    assert any("'x'" in n for n in notes)


def test_a_plain_survey_has_no_notes():
    _template, notes = _import({"type": "rating", "name": "r", "title": "R"}, {"type": "text", "name": "t", "title": "T"})
    assert notes == []


def test_hidden_item_is_a_note():
    _template, notes = _import({"type": "text", "name": "t", "title": "T", "visible": False})
    assert any("'t'" in n and "visible" in n for n in notes)
