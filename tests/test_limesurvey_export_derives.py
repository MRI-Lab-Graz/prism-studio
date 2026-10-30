"""A template carries no export settings: the LimeSurvey export derives question type, mandatory, help ...
from the generic item fields, and the user overrides them for one export only (the customizer's
toolOverrides). An old file whose items still carry a LimeSurvey block exports exactly like its stripped form."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import defusedxml.ElementTree as DET  # noqa: E402

FOUR = {str(i): {"en": f"level {i}"} for i in range(1, 5)}


def _old_template():
    return {
        "Study": {"OriginalName": "Old"},
        "I18n": {"Languages": ["en"], "DefaultLanguage": "en"},
        "q1": {
            "Description": {"en": "Question one"},
            "Levels": FOUR,
            "LimeSurvey": {
                "mandatory": False,
                "validation": {"min": 1, "max": 5},
                "relevance": "q0==1",
                "helpText": "h",
                "other": True,
                "questionType": "!",
                "inputWidth": "30",
                "columnName": "Q1",
            },
        },
    }


def _write(tmp_path, template, name="survey-old.json"):
    path = tmp_path / name
    path.write_text(json.dumps(template), encoding="utf-8")
    return path


def _types(xml):
    root = DET.fromstring(xml)
    return {q.findtext("title"): q.findtext("type") for q in root.findall("questions/rows/row")}


def test_old_block_exports_like_stripped(tmp_path):
    from src.limesurvey_exporter import generate_lss
    from src.survey_export_settings import strip_export_settings

    old = _write(tmp_path, _old_template())
    stripped_dir = tmp_path / "stripped"
    stripped_dir.mkdir()
    stripped = _write(stripped_dir, strip_export_settings(_old_template())[0])

    # same file name: the source path is not part of the .lss
    assert generate_lss([str(old)]) == generate_lss([str(stripped)])
    assert _types(generate_lss([str(old)]))["q1"] == "L"


def test_question_type_is_derived():
    from src.limesurvey_exporter import ls_question_type

    assert ls_question_type({"Levels": FOUR}) == "L"
    assert ls_question_type({"Levels": {str(i): str(i) for i in range(12)}}) == "!"
    assert ls_question_type({"DataType": "integer"}) == "N"
    assert ls_question_type({"Levels": FOUR, "LimeSurvey": {"questionType": "!"}}) == "L"


def test_customizer_payload_carries_derived_type_and_no_template_overrides(tmp_path):
    from src.survey_customizer import build_customizer_groups

    path = _write(tmp_path, _old_template())
    question = build_customizer_groups([{"path": str(path)}])[0]["questions"][0]
    assert question["questionType"] == "L"
    assert question["toolOverrides"] == {}
    assert question["mandatory"] is False  # the old LimeSurvey.mandatory, read as the generic Mandatory
    assert question["originalData"]["LimeSurvey"] == {"columnName": "Q1"}


def test_override_wins(tmp_path):
    from src.limesurvey_exporter import generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    path = _write(tmp_path, {**_old_template(), "q1": {"Description": {"en": "Q"}, "Levels": FOUR}})
    groups = build_customizer_groups([{"path": str(path)}])
    groups[0]["questions"][0]["toolOverrides"] = {"questionType": "!"}
    assert _types(generate_lss_from_customization(groups))["q1"] == "!"
    assert json.loads(path.read_text(encoding="utf-8"))["q1"] == {"Description": {"en": "Q"}, "Levels": FOUR}
