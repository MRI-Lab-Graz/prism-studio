from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from flask import Flask, session


def _build_app_and_handlers():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    handlers = importlib.import_module(
        "src.web.blueprints.tools_template_editor_blueprint"
    )
    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = "test-secret"
    return app, handlers


def test_template_editor_save_writes_only_to_project_code_library(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    legacy_path = tmp_path / "survey_library" / "survey" / "survey-mood.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    monkeypatch.setattr(handlers, "_validate_against_schema", lambda **kwargs: [])

    template = {
        "Study": {"TaskName": "mood", "ShortName": "mood"},
        "Technical": {"Language": "en"},
        "MOOD01": {"Description": "I feel calm.", "MinValue": 1, "MaxValue": 5},
    }

    with app.test_request_context(
        "/api/template-editor/save",
        method="POST",
        json={
            "modality": "survey",
            "schema_version": "stable",
            "filename": "survey-mood.json",
            "template": template,
        },
    ):
        session["current_project_path"] = str(tmp_path)
        response, status_code = handlers.api_template_editor_save()

    assert status_code == 200
    data = response.get_json()
    assert data["ok"] is True

    saved_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == template
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }