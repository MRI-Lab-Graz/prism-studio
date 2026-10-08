"""Pavlovia (SurveyJS) survey JSON -> PRISM templates, one per page."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.converters.pavlovia_import import (
    is_pavlovia_survey,
    list_pavlovia_questionnaires,
    pavlovia_questionnaire_template,
)

FIXTURE = Path(__file__).parent / "data" / "pavlovia_survey.json"


@pytest.fixture
def survey():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_detects_surveyjs_but_not_a_prism_template(survey):
    assert is_pavlovia_survey(survey)
    assert not is_pavlovia_survey({"Technical": {}, "Study": {}})
    assert not is_pavlovia_survey([1, 2])


def test_lists_one_questionnaire_per_page(survey):
    listing = list_pavlovia_questionnaires(survey)
    assert [(q["key"], q["name"], q["item_count"]) for q in listing] == [
        ("p1", "Basics", 5), ("p2", "ARSQ", 2), ("p3", "Danke", 1),
    ]


def test_survey_split_is_one_questionnaire(survey):
    listing = list_pavlovia_questionnaires(survey, split="survey")
    assert [(q["key"], q["item_count"]) for q in listing] == [("survey", 8)]


def test_unknown_key_names_the_valid_ones(survey):
    with pytest.raises(ValueError, match="Valid keys: p1, p2, p3"):
        pavlovia_questionnaire_template(survey, "p9")


def test_template_metadata(survey):
    t = pavlovia_questionnaire_template(survey, "p2")
    assert t["Study"]["TaskName"] == "arsq"
    assert t["Study"]["OriginalName"] == "ARSQ"
    assert t["Technical"]["SoftwarePlatform"] == "Pavlovia"
    assert t["Technical"]["AdministrationMethod"] == "online"


def test_rating_without_rate_values_is_one_to_five(survey):
    item = pavlovia_questionnaire_template(survey, "p2")["ARSQ1"]
    assert item["Description"] == {"en": "Ich hatte schnell wechselnde Gedanken"}  # no locale in file -> en
    assert list(item["Levels"]) == ["1", "2", "3", "4", "5"]


def test_levels_keyed_by_stored_value_labelled_by_text(survey):
    t = pavlovia_questionnaire_template(survey, "p1")
    lang = t["Technical"]["Language"]
    assert t["Kaffee"]["Levels"] == {"viel weniger": {lang: "Ja"}, "weniger": {lang: "Nein"}}
    assert list(t["KaffeeHeute"]["Levels"]) == ["viel weniger", "weniger", "gleich", "mehr", "viel mehr"]
    assert t["sesID"]["Levels"]["Item 2"] == {lang: "2"}


def test_numeric_text_item_gets_datatype_and_range(survey):
    item = pavlovia_questionnaire_template(survey, "p1")["studyID"]
    assert item["DataType"] == "integer"
    assert (item["MinValue"], item["MaxValue"]) == (130, 200)


def test_boolean_has_two_levels(survey):
    t = pavlovia_questionnaire_template(survey, "p3")
    assert t["question1"]["Levels"] == {"true": {t["Technical"]["Language"]: "Ja"},
                                        "false": {t["Technical"]["Language"]: "Nein"}}


def test_visible_if_becomes_relevance_and_required_becomes_mandatory(survey):
    t = pavlovia_questionnaire_template(survey, "p1")
    assert t["KaffeeHeute"]["Relevance"] == "{Kaffee} = 'viel weniger'"
    assert "Relevance" not in t["Kaffee"]
    assert t["Kaffee"]["Mandatory"] is False  # SurveyJS default; the PRISM default is True


def test_descriptions_go_to_instructions(survey):
    study = pavlovia_questionnaire_template(survey, "p1")["Study"]
    assert "Im Vergleich zu einem durchschnittlichen Tag" in study["Instructions"]["en"]


def test_hidden_item_is_warned(survey, capsys):
    pavlovia_questionnaire_template(survey, "p1")
    out = capsys.readouterr().out
    assert "WARNING" in out and "studyID" in out and "visible" in out


def test_non_surveyjs_input_is_rejected():
    with pytest.raises(ValueError, match="SurveyJS"):
        list_pavlovia_questionnaires({"Technical": {}})


# --- CLI: survey import-pavlovia ------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from src.cli.commands.survey import cmd_survey_import_pavlovia  # noqa: E402


def _args(**kw):
    values = dict(input=str(FIXTURE), split="page", list=False, select=None, output=None, project=None,
                  software_version=None)
    values.update(kw)
    return SimpleNamespace(**values)


def test_cli_lists_without_select(capsys, tmp_path):
    cmd_survey_import_pavlovia(_args())
    out = capsys.readouterr().out
    assert "p1" in out and "Basics" in out and "p3" in out


def test_cli_writes_selected_pages(tmp_path):
    cmd_survey_import_pavlovia(_args(select=["p1", "p2"], output=str(tmp_path)))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["survey-arsq.json", "survey-basics.json"]
    written = json.loads((tmp_path / "survey-arsq.json").read_text(encoding="utf-8"))
    assert written["Technical"]["SoftwarePlatform"] == "Pavlovia"


def test_cli_software_version_is_written_to_every_template(tmp_path):
    cmd_survey_import_pavlovia(_args(select=["all"], output=str(tmp_path), software_version="2025.1"))
    versions = {json.loads(p.read_text(encoding="utf-8"))["Technical"]["SoftwareVersion"] for p in tmp_path.iterdir()}
    assert versions == {"2025.1"}


def test_template_without_software_version_has_none(survey):
    assert "SoftwareVersion" not in pavlovia_questionnaire_template(survey, "p1")["Technical"]


def test_cli_select_all_and_no_overwrite(tmp_path):
    cmd_survey_import_pavlovia(_args(select=["all"], output=str(tmp_path)))
    assert len(list(tmp_path.iterdir())) == 3
    with pytest.raises(SystemExit):
        cmd_survey_import_pavlovia(_args(select=["p1"], output=str(tmp_path)))


def test_cli_output_without_select_fails(tmp_path):
    with pytest.raises(SystemExit):
        cmd_survey_import_pavlovia(_args(output=str(tmp_path)))


def test_cli_rejects_non_surveyjs_file(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text('{"Technical": {}}')
    with pytest.raises(SystemExit):
        cmd_survey_import_pavlovia(_args(input=str(bad)))


# --- route: POST /api/template-editor/import-pavlovia ----------------------------

import io  # noqa: E402
import os  # noqa: E402

from flask import Flask  # noqa: E402


def _client():
    import importlib

    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def _post(data=None, content=None):
    form = {"file": (io.BytesIO(content or FIXTURE.read_bytes()), "survey.json"), **(data or {})}
    return _client().post("/api/template-editor/import-pavlovia", data=form, content_type="multipart/form-data")


def test_route_lists_pages_and_prints_cli_equivalent(capsys):
    response = _post()
    assert response.status_code == 200
    assert [q["key"] for q in response.get_json()["questionnaires"]] == ["p1", "p2", "p3"]
    assert "prism_tools.py survey import-pavlovia --input survey.json --split page" in capsys.readouterr().out


def test_route_loads_one_page():
    body = _post({"key": "p2"}).get_json()
    assert body["suggested_filename"] == "survey-arsq.json"
    assert body["item_count"] == 2
    assert "ARSQ1" in body["template"] and "library_match" in body


def test_route_bad_input_is_400():
    assert _post({"key": "p9"}).status_code == 400
    assert _post(content=b'{"Technical": {}}').status_code == 400
    assert _post(content=b"not json").status_code == 400
