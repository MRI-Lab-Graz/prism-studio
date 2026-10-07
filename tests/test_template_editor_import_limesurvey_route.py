"""POST /api/template-editor/import-limesurvey: list, then load one questionnaire."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from flask import Flask

from src.converters import survey_templates as st
from test_library_wording_match import drop_task_name, library_file

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"


def _client():
    import importlib

    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def _post(client, data=None, name="survey.lss", content=None):
    form = {"file": (io.BytesIO(content or FIXTURE.read_bytes()), name), **(data or {})}
    return client.post("/api/template-editor/import-limesurvey", data=form,
                       content_type="multipart/form-data")


def test_lists_questionnaires_and_prints_cli_equivalent(capsys):
    response = _post(_client())

    assert response.status_code == 200
    body = response.get_json()
    assert [q["key"] for q in body["questionnaires"]] == ["g10", "g20", "g30", "g40"]
    assert body["split"] == "group"
    out = capsys.readouterr().out
    assert "prism_tools.py survey import-limesurvey --input survey.lss --split group" in out


def test_loads_one_questionnaire():
    response = _post(_client(), {"split": "group", "key": "g30"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["item_count"] == 2
    assert body["suggested_filename"] == "survey-ads.json"
    assert body["languages"] == ["de"]
    assert "ADS1_1" in body["template"]


def test_bad_input_is_a_400_with_message():
    client = _client()

    assert _post(client, {"key": "g99"}).get_json()["error"].startswith("No questionnaire 'g99'")
    assert _post(client, {"key": "g99"}).status_code == 400
    assert _post(client, name="x.lsa", content=b"junk").status_code == 400
    assert client.post("/api/template-editor/import-limesurvey", data={}).status_code == 400


def test_unexpected_failure_is_a_json_500(monkeypatch):
    import src.converters.limesurvey as limesurvey

    def boom(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(limesurvey, "list_limesurvey_questionnaires", boom)
    response = _post(_client())

    assert response.status_code == 500
    assert "kaputt" in response.get_json()["error"]


ADS = ["war ich bedrückt", "war ich müde"]
ADS_LEVELS = {"0": "selten", "1": "meistens"}


@pytest.fixture
def library(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    (project / "code" / "library" / "survey").mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS)
    return str(project)


def test_list_carries_the_library_match_without_the_local_path(library):
    body = _post(_client(), {"project_path": library}).get_json()

    entries = {q["key"]: q for q in body["questionnaires"]}
    match = entries["g30"]["library_match"]
    assert match["confidence"] == "exact" and match["source"] == "project"
    assert match["id_map"] == {"ADS1_1": "ads_01", "ADS1_2": "ads_02"}
    assert "template_path" not in match and library not in json.dumps(body)
    assert entries["g20"]["library_match"] is None


def test_key_call_returns_the_match_next_to_the_imported_template(library):
    body = _post(_client(), {"project_path": library, "key": "g30"}).get_json()

    assert "ADS1_1" in body["template"]
    assert body["library_match"]["adoptable"] is True


def test_use_library_returns_the_library_template_with_aliases(library):
    body = _post(_client(), {"project_path": library, "key": "g30", "use_library": "1"}).get_json()

    assert body["template"]["ads_01"]["Aliases"] == ["ADS1_1"]
    assert "ADS1_1" not in body["template"]
    assert body["suggested_filename"] == "survey-ads.json"
    assert body["item_count"] == 2


def test_use_library_without_a_one_to_one_match_is_a_400(library):
    response = _post(_client(), {"project_path": library, "key": "g20", "use_library": "1"})

    assert response.status_code == 400
    assert "one-to-one" in response.get_json()["error"]


def test_use_library_works_for_a_library_template_without_task_name(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    drop_task_name(library_file(global_dir, name="gad", texts=ADS, levels=ADS_LEVELS))
    before = {p.name: p.read_bytes() for p in global_dir.iterdir()}

    response = _post(_client(), {"key": "g30", "use_library": "1"})

    assert response.status_code == 200
    assert response.get_json()["suggested_filename"] == "survey-gad.json"
    assert {p.name: p.read_bytes() for p in global_dir.iterdir()} == before
