from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

from flask import Flask, session


def _build_app() -> Flask:
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)
    return app


def test_limesurvey_save_to_project_writes_only_to_code_library(tmp_path):
    app = _build_app()
    handlers = importlib.import_module(
        "src.web.blueprints.tools_post_conversion_handlers"
    )

    legacy_path = tmp_path / "survey_library" / "survey-legacy.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    payload = {
        "templates": [
            {
                "filename": "survey-mood.json",
                "content": {
                    "Study": {"TaskName": "mood"},
                    "Technical": {"Language": "en"},
                },
            }
        ]
    }

    with app.app_context():
        response = handlers.handle_limesurvey_save_to_project(str(tmp_path), payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    saved_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "Study": {"TaskName": "mood"},
        "Technical": {"Language": "en"},
    }
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }


def test_save_unmatched_template_writes_only_to_code_library(tmp_path):
    app = _build_app()
    handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")

    legacy_path = tmp_path / "survey_library" / "survey" / "survey-mood.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    prism_json = {
        "Study": {"TaskName": "mood"},
        "Technical": {"Language": "en"},
        "MOOD01": {"Description": "I feel calm."},
        "_ephemeral": {"ignore": True},
    }

    with app.test_request_context(
        "/api/save-unmatched-template",
        method="POST",
        json={"task_key": "mood", "prism_json": prism_json},
    ):
        session["current_project_path"] = str(tmp_path)
        response = handlers.api_save_unmatched_template()

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    saved_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "Study": {"TaskName": "mood"},
        "Technical": {"Language": "en"},
        "MOOD01": {"Description": "I feel calm."},
    }
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }


def test_survey_customizer_project_copy_targets_code_library(tmp_path, monkeypatch):
    app = _build_app()
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    fake_exporter = types.ModuleType("src.limesurvey_exporter")

    def _generate_lss_from_customization(**kwargs):
        Path(kwargs["output_path"]).write_text("<lss />", encoding="utf-8")

    fake_exporter.generate_lss_from_customization = _generate_lss_from_customization
    monkeypatch.setitem(sys.modules, "src.limesurvey_exporter", fake_exporter)

    source_path = tmp_path / "survey_library" / "survey-mood.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    payload = {
        "exportFormat": "limesurvey",
        "survey": {"title": "Mood Study", "language": "en"},
        "groups": [{"sourceFile": str(source_path)}],
        "exportOptions": {},
        "saveToProject": True,
    }

    with app.test_request_context("/survey-customizer/export", method="POST"):
        response = handlers.handle_survey_customizer_export(payload, str(tmp_path))

    assert response.status_code == 200
    assert response.headers["X-Templates-Saved"] == "1"

    saved_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }
    assert json.loads(source_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }


def test_survey_customizer_project_copy_normalizes_project_json_path(
    tmp_path, monkeypatch
):
    app = _build_app()
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    fake_exporter = types.ModuleType("src.limesurvey_exporter")

    def _generate_lss_from_customization(**kwargs):
        Path(kwargs["output_path"]).write_text("<lss />", encoding="utf-8")

    fake_exporter.generate_lss_from_customization = _generate_lss_from_customization
    monkeypatch.setitem(sys.modules, "src.limesurvey_exporter", fake_exporter)

    source_path = tmp_path / "survey_library" / "survey-mood.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    target_project = tmp_path / "target-project"
    target_project.mkdir(parents=True)
    (target_project / "project.json").write_text("{}", encoding="utf-8")

    payload = {
        "exportFormat": "limesurvey",
        "survey": {"title": "Mood Study", "language": "en"},
        "groups": [{"sourceFile": str(source_path)}],
        "exportOptions": {},
        "saveToProject": True,
    }

    with app.test_request_context("/survey-customizer/export", method="POST"):
        response = handlers.handle_survey_customizer_export(
            payload, str(target_project / "project.json")
        )

    assert response.status_code == 200
    assert response.headers["X-Templates-Saved"] == "1"

    saved_path = target_project / "code" / "library" / "survey" / "survey-mood.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "location": "legacy-root"
    }


def test_survey_customizer_project_copy_rejects_stale_project_path(
    tmp_path, monkeypatch
):
    app = _build_app()
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    fake_exporter = types.ModuleType("src.limesurvey_exporter")

    def _generate_lss_from_customization(**kwargs):
        Path(kwargs["output_path"]).write_text("<lss />", encoding="utf-8")

    fake_exporter.generate_lss_from_customization = _generate_lss_from_customization
    monkeypatch.setitem(sys.modules, "src.limesurvey_exporter", fake_exporter)

    source_path = tmp_path / "survey_library" / "survey-mood.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    stale_project = tmp_path / "missing-project"
    payload = {
        "exportFormat": "limesurvey",
        "survey": {"title": "Mood Study", "language": "en"},
        "groups": [{"sourceFile": str(source_path)}],
        "exportOptions": {},
        "saveToProject": True,
    }

    with app.test_request_context("/survey-customizer/export", method="POST"):
        response = handlers.handle_survey_customizer_export(payload, str(stale_project))

    error_response, status_code = response
    assert status_code == 400
    payload = error_response.get_json()
    assert "no longer exists" in payload["error"].lower()
    assert not stale_project.exists()


def test_survey_customizer_project_copy_requires_project_path(tmp_path, monkeypatch):
    app = _build_app()
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    fake_exporter = types.ModuleType("src.limesurvey_exporter")

    def _generate_lss_from_customization(**kwargs):
        Path(kwargs["output_path"]).write_text("<lss />", encoding="utf-8")

    fake_exporter.generate_lss_from_customization = _generate_lss_from_customization
    monkeypatch.setitem(sys.modules, "src.limesurvey_exporter", fake_exporter)

    source_path = tmp_path / "survey_library" / "survey-mood.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    payload = {
        "exportFormat": "limesurvey",
        "survey": {"title": "Mood Study", "language": "en"},
        "groups": [{"sourceFile": str(source_path)}],
        "exportOptions": {},
        "saveToProject": True,
    }

    with app.test_request_context("/survey-customizer/export", method="POST"):
        response = handlers.handle_survey_customizer_export(payload, "")

    error_response, status_code = response
    assert status_code == 400
    payload = error_response.get_json()
    assert "no active project selected" in payload["error"].lower()
