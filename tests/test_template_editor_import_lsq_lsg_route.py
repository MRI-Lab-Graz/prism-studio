"""Integration test for POST /api/template-editor/import-lsq-lsg.

Regression coverage for the bug documented in
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md: this route imported
parse_lsq_xml/parse_lsg_xml from src.converters.limesurvey, which had been
silently dropped from that module during a canonicalization refactor. The
route 500'd on every real click; prior tests only grepped the JS source and
never exercised this handler.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from flask import Flask


def _build_app():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    import importlib

    blueprint_module = importlib.import_module(
        "src.web.blueprints.tools_template_editor_blueprint"
    )
    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)
    app.register_blueprint(blueprint_module.tools_template_editor_bp)
    return app


_MINIMAL_LSQ = b"""<?xml version="1.0" encoding="UTF-8"?>
<document>
  <questions><rows>
    <row>
      <qid>10</qid>
      <gid>1</gid>
      <type>L</type>
      <title>MOOD</title>
      <question>How do you feel today?</question>
      <question_order>1</question_order>
      <mandatory>Y</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <preg></preg>
    </row>
  </rows></questions>
  <answers><rows>
    <row><qid>10</qid><code>1</code><answer>Good</answer></row>
    <row><qid>10</qid><code>2</code><answer>Bad</answer></row>
  </rows></answers>
  <question_attributes><rows></rows></question_attributes>
  <subquestions><rows></rows></subquestions>
</document>
"""


def test_import_lsq_returns_template_not_500():
    app = _build_app()
    with app.test_client() as client:
        response = client.post(
            "/api/template-editor/import-lsq-lsg",
            data={"file": (io.BytesIO(_MINIMAL_LSQ), "question.lsq")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["source_type"] == "lsq"
    assert payload["item_count"] == 1
    assert "MOOD" in payload["template"]


def test_import_lsg_returns_template_not_500():
    app = _build_app()
    lsg_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<document>
  <groups><rows>
    <row><gid>1</gid><group_name>Wellbeing</group_name><group_order>1</group_order></row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>100</qid><gid>1</gid><type>S</type><title>SLEEP</title>
      <question>How did you sleep?</question><question_order>1</question_order>
      <mandatory>N</mandatory><parent_qid>0</parent_qid><other>N</other>
    </row>
  </rows></questions>
  <answers><rows></rows></answers>
  <question_attributes><rows></rows></question_attributes>
  <subquestions><rows></rows></subquestions>
</document>
"""
    with app.test_client() as client:
        response = client.post(
            "/api/template-editor/import-lsq-lsg",
            data={"file": (io.BytesIO(lsg_bytes), "group.lsg")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["source_type"] == "lsg"
    assert "SLEEP" in payload["template"]


def test_rejects_unsupported_extension():
    app = _build_app()
    with app.test_client() as client:
        response = client.post(
            "/api/template-editor/import-lsq-lsg",
            data={"file": (io.BytesIO(b"whatever"), "notes.txt")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    assert "Unsupported file type" in response.get_json()["error"]


def test_rejects_missing_file():
    app = _build_app()
    with app.test_client() as client:
        response = client.post("/api/template-editor/import-lsq-lsg", data={})

    assert response.status_code == 400
