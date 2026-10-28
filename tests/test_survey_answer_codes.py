"""Answer codes a survey author chose (ADS0..ADS3) instead of the scale's numbers.

Nothing is recoded unasked: the import keeps LimeSurvey's codes and says they are not
numbers; the user gives them numbers in the template (editor or `survey answer-codes`),
pre-filled with a suggestion. The template then holds the numbers as Levels and the stored
codes in LimeSurvey.answerCodes, and conversion reads each stored code as its number.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

ADS = {"ADS0": "0", "ADS1": "1", "ADS2": "2", "ADS3": "3"}


def _levels(*codes):
    return {c: {"de": f"label {c}"} for c in codes}


def _template():
    items = {f"ADS1_{i}": {"Description": {"de": f"q{i}"}, "Levels": _levels(*ADS),
                           "LimeSurvey": {"columnName": f"ADS1[{i}]"}} for i in (1, 2)}
    return {
        "Study": {"TaskName": "ads"},
        **items,
        "yn": {"Description": {"de": "yn"}, "Levels": _levels("Y", "N")},
        "pss": {"Description": {"de": "pss"}, "Levels": _levels("1", "2")},
    }


def test_suggestions_list_codes_that_are_not_numbers():
    from src.survey_answer_codes import suggest_answer_numbers

    suggestions = suggest_answer_numbers(_template())
    assert {"codes": ADS, "items": ["ADS1_1", "ADS1_2"]} in suggestions
    assert {"codes": {"Y": "", "N": ""}, "items": ["yn"]} in suggestions  # nothing to suggest: left blank
    assert len(suggestions) == 2  # pss already has numbers


def test_apply_renames_levels_and_keeps_the_stored_codes():
    from src.survey_answer_codes import apply_answer_numbers

    template = _template()
    changed = apply_answer_numbers(template, ADS)

    assert changed == ["ADS1_1", "ADS1_2"]
    item = template["ADS1_1"]
    assert list(item["Levels"]) == ["0", "1", "2", "3"]
    assert item["Levels"]["2"] == {"de": "label ADS2"}
    assert item["LimeSurvey"] == {"columnName": "ADS1[1]", "answerCodes": {v: k for k, v in ADS.items()}}
    assert set(template["yn"]["Levels"]) == {"Y", "N"}


def test_applying_again_keeps_pointing_at_the_stored_code():
    from src.survey_answer_codes import apply_answer_numbers

    template = _template()
    apply_answer_numbers(template, ADS)
    apply_answer_numbers(template, {"0": "1", "1": "2", "2": "3", "3": "4"})
    assert template["ADS1_1"]["LimeSurvey"]["answerCodes"] == {"1": "ADS0", "2": "ADS1", "3": "ADS2", "4": "ADS3"}


@pytest.mark.parametrize("mapping", [{**ADS, "ADS1": "0"}, {**ADS, "ADS0": "x"}, {"ADS0": "0"}])
def test_apply_refuses_duplicates_non_numbers_and_partial_maps(mapping):
    from src.survey_answer_codes import apply_answer_numbers

    template = _template()
    with pytest.raises(ValueError):
        apply_answer_numbers(template, mapping)
    assert template == _template()


def test_convert_reads_the_stored_code_as_its_number():
    from src.converters.survey import _validate_survey_item_value
    from src.survey_answer_codes import apply_answer_numbers

    template = _template()
    apply_answer_numbers(template, ADS)
    value = _validate_survey_item_value(
        item_id="ADS1_1", val="ADS2", item_schema=template["ADS1_1"], sub_id="sub-1", task="ads",
        strict_levels=True, items_using_tolerance={}, normalize_fn=lambda v: str(v).strip(),
        is_missing_fn=lambda v: v in (None, ""),
    )
    assert value == "2"


def test_import_keeps_codes_and_notes_they_are_not_numbers():
    from src.converters.limesurvey import limesurvey_questionnaire

    from tests.test_limesurvey_row_types import LSS  # ranking options coded A1..A3

    template, notes = limesurvey_questionnaire(LSS, "g1")
    assert set(template["rank_1"]["Levels"]) == {"A1", "A2", "A3"}
    assert any(" / rank:" in n and "not numbers" in n for n in notes), notes


def test_cli_lists_then_applies(tmp_path, capsys):
    from src.cli.commands.survey import cmd_survey_answer_codes

    path = tmp_path / "survey-ads.json"
    path.write_text(json.dumps(_template()), encoding="utf-8")

    cmd_survey_answer_codes(SimpleNamespace(template=str(path), set=None, json=True))
    assert json.loads(capsys.readouterr().out)["suggestions"][0]["codes"] == ADS

    cmd_survey_answer_codes(SimpleNamespace(template=str(path), set="ADS0=0,ADS1=1,ADS2=2,ADS3=3", json=True))
    assert json.loads(capsys.readouterr().out)["changed"] == ["ADS1_1", "ADS1_2"]
    assert list(json.loads(path.read_text(encoding="utf-8"))["ADS1_1"]["Levels"]) == ["0", "1", "2", "3"]


def _editor_post(body):
    import os

    from flask import Flask

    from src.web.blueprints.tools_template_editor_blueprint import tools_template_editor_bp

    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(tools_template_editor_bp)
    return app.test_client().post("/api/template-editor/answer-codes", json=body)


def test_editor_route_suggests_then_applies():
    listed = _editor_post({"template": _template()}).get_json()
    assert listed["suggestions"][0] == {"codes": ADS, "items": ["ADS1_1", "ADS1_2"]}

    applied = _editor_post({"template": _template(), "codes": ADS}).get_json()
    assert applied["changed"] == ["ADS1_1", "ADS1_2"]
    assert list(applied["template"]["ADS1_1"]["Levels"]) == ["0", "1", "2", "3"]


def test_editor_route_refuses_a_bad_mapping():
    response = _editor_post({"template": _template(), "codes": {**ADS, "ADS1": "0"}})
    assert response.status_code == 400
    assert "distinct whole numbers" in response.get_json()["error"]
