"""POST /api/template-editor/share-mail: same mail as `library share-template`."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from flask import Flask


def _client():
    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def test_returns_the_share_mail():
    response = _client().post("/api/template-editor/share-mail",
                              json={"filename": "survey-x.json", "template": {"Study": {"OriginalName": "X"}}})
    assert response.status_code == 200
    body = response.get_json()
    assert body["to"] == "mri-lab@uni-graz.at" and body["mailto"].startswith("mailto:")


def test_rejects_a_non_object_template_and_a_missing_filename():
    client = _client()
    assert client.post("/api/template-editor/share-mail", json={"filename": "a.json", "template": []}).status_code == 400
    assert client.post("/api/template-editor/share-mail", json={"template": {}}).status_code == 400
