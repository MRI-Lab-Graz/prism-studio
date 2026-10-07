"""POST /api/template-editor/import-limesurvey: list, then load one questionnaire."""

from __future__ import annotations

import io
import os
from pathlib import Path

from flask import Flask

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
