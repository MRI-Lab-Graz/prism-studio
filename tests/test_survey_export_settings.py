"""strip_export_settings: a template holds no LimeSurvey export settings (only columnName/answerCodes)."""

import copy

import pytest

from src.limesurvey_attributes import LS_DESIGN_ATTRIBUTES
from src.survey_export_settings import KEPT_LIMESURVEY_KEYS, strip_export_settings


def _strip(item_ls, **item):
    out, _ = strip_export_settings({"q1": {"Description": "x", **item, "LimeSurvey": item_ls}})
    return out["q1"]


def test_mandatory_becomes_generic():
    q = _strip({"mandatory": False})
    assert q["Mandatory"] is False
    assert "LimeSurvey" not in q


def test_validation_min_max_become_generic_integer_only_dropped():
    q = _strip({"validation": {"min": 1, "max": 7, "integerOnly": True}})
    assert (q["MinValue"], q["MaxValue"]) == (1, 7)
    assert "LimeSurvey" not in q


def test_relevance_mapped_unless_always_true():
    assert _strip({"relevance": "q0 == 1"})["Relevance"] == "q0 == 1"
    assert "Relevance" not in _strip({"relevance": "1"})


def test_help_and_other_become_generic():
    q = _strip({"helpText": {"en": "h"}, "other": True})
    assert q["Help"] == {"en": "h"}
    assert q["OtherOption"] == {"enabled": True}


@pytest.mark.parametrize(
    "key",
    ["questionType", "questionTypeName", "inputWidth", "displayRows", "hidden", "equation", "unknownKey", *LS_DESIGN_ATTRIBUTES],
)
def test_display_settings_are_dropped(key):
    q = _strip({key: "v", "columnName": "Q1"})
    assert q["LimeSurvey"] == {"columnName": "Q1"}
    assert key not in q


def test_existing_generic_value_wins():
    q = _strip(
        {"mandatory": False, "helpText": "new", "other": True, "validation": {"min": 5, "max": 9}},
        Mandatory=True,
        Help="old",
        OtherOption={"enabled": False, "x": 1},
        MinValue=0,
    )
    assert q["Mandatory"] is True
    assert q["Help"] == "old"
    assert q["OtherOption"] == {"enabled": False, "x": 1}
    assert q["MinValue"] == 0
    assert q["MaxValue"] == 9


def test_column_name_and_answer_codes_kept():
    assert KEPT_LIMESURVEY_KEYS == ("columnName", "answerCodes")
    q = _strip({"columnName": "Q1[SQ001]", "answerCodes": {"1": "A1"}, "questionType": "L"})
    assert q["LimeSurvey"] == {"columnName": "Q1[SQ001]", "answerCodes": {"1": "A1"}}


def test_non_dict_items_and_blocks_and_reserved_sections_untouched():
    t = {
        "Technical": {"LimeSurvey": {"questionType": "L"}},
        "LimeSurvey": {"questionType": "L"},
        "note": "text",
        "q2": {"Description": "d", "LimeSurvey": "weird"},
        "q3": ["not", "a", "dict"],
    }
    out, report = strip_export_settings(t)
    assert out == t
    assert report == []


def test_report_one_entry_per_changed_item():
    t = {
        "q1": {"Description": "x", "LimeSurvey": {"questionType": "L", "inputWidth": "5", "validation": {"min": 1}}},
        "q2": {"Description": "y", "LimeSurvey": {"columnName": "Q2"}},
        "q3": {"Description": "z"},
    }
    _, report = strip_export_settings(t)
    assert report == ["q1: inputWidth, questionType, validation"]
    assert strip_export_settings({"q2": t["q2"]})[1] == []


def test_input_not_mutated():
    t = {"q1": {"Description": "x", "LimeSurvey": {"mandatory": True, "validation": {"min": 1}}}}
    before = copy.deepcopy(t)
    strip_export_settings(t)
    assert t == before
