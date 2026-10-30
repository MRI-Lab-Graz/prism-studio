from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, session

from template_fixtures import library_template, project_template


def _build_app_and_handlers():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    handlers = importlib.import_module(
        "src.web.blueprints.tools_template_editor_blueprint"
    )
    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)
    return app, handlers


def _save(app, handlers, session_project, **payload):
    body = {"modality": "survey", "schema_version": "stable", **payload}
    with app.test_request_context("/api/template-editor/save", method="POST", json=body):
        session["current_project_path"] = str(session_project)
        return handlers.api_template_editor_save()


def test_template_editor_save_writes_only_to_project_code_library(tmp_path):
    app, handlers = _build_app_and_handlers()

    legacy_path = tmp_path / "survey_library" / "survey" / "survey-mood.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"location": "legacy-root"}', encoding="utf-8")

    response, status_code = _save(app, handlers, tmp_path, filename="survey-mood.json", template=project_template("mood"))

    assert status_code == 200
    assert response.get_json()["ok"] is True
    saved_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    assert json.loads(saved_path.read_text(encoding="utf-8"))["Study"]["TaskName"] == "mood"
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {"location": "legacy-root"}


def test_template_editor_save_normalizes_legacy_platform_for_paper(tmp_path):
    app, handlers = _build_app_and_handlers()
    template = project_template("stai")
    template["Technical"].update(AdministrationMethod="paper", SoftwarePlatform="Legacy/Imported", SoftwareVersion="legacy")

    response, status_code = _save(app, handlers, tmp_path, filename="survey-stai.json", template=template)

    assert status_code == 200, response.get_json()
    saved = json.loads((tmp_path / "code" / "library" / "survey" / "survey-stai.json").read_text(encoding="utf-8"))
    assert saved["Technical"]["SoftwarePlatform"] == "Paper and Pencil"
    assert saved["Technical"]["SoftwareVersion"] == ""


def test_template_editor_save_relaxes_schema_when_copying_global_template(tmp_path):
    """A library template has no project fields (platform, administration method): saving it as a copy of a global one is fine."""
    app, handlers = _build_app_and_handlers()
    template = library_template("aai")
    template["Technical"].pop("SoftwarePlatform", None)
    template["Technical"].pop("AdministrationMethod", None)

    response, status_code = _save(app, handlers, tmp_path, filename="survey-aai.json", is_global=True, template=template)

    assert status_code == 200, response.get_json()
    assert response.get_json()["ok"] is True


def test_template_editor_save_warns_about_missing_project_fields_when_not_copying_global_template(tmp_path):
    app, handlers = _build_app_and_handlers()
    template = library_template("aai")
    template["Technical"].pop("SoftwarePlatform", None)
    template["Technical"].pop("AdministrationMethod", None)

    response, status_code = _save(app, handlers, tmp_path, filename="survey-aai.json", template=template)

    assert status_code == 200
    paths = {m["path"] for m in response.get_json()["missing"]}
    assert {"Technical/SoftwarePlatform", "Technical/AdministrationMethod"} <= paths


def test_template_editor_save_requires_explicit_overwrite_confirmation(tmp_path):
    app, handlers = _build_app_and_handlers()
    existing_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text('{"status": "original"}', encoding="utf-8")

    response, status_code = _save(app, handlers, tmp_path, filename="survey-mood.json", template=project_template("mood"))

    assert status_code == 409
    payload = response.get_json()
    assert payload["error"] == 'Template "survey-mood.json" already exists in the project library'
    assert payload["code"] == "file_exists"
    assert json.loads(existing_path.read_text(encoding="utf-8")) == {"status": "original"}


def test_template_editor_save_allows_confirmed_overwrite(tmp_path):
    app, handlers = _build_app_and_handlers()
    existing_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text('{"status": "original"}', encoding="utf-8")

    response, status_code = _save(
        app, handlers, tmp_path, filename="survey-mood.json", allow_overwrite=True, template=project_template("mood")
    )

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert json.loads(existing_path.read_text(encoding="utf-8"))["Study"]["TaskName"] == "mood"


def test_template_editor_save_can_target_explicit_project_path(tmp_path):
    app, handlers = _build_app_and_handlers()
    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    primary_project.mkdir()
    target_project.mkdir()

    response, status_code = _save(
        app, handlers, primary_project, filename="survey-mood.json", project_path=str(target_project),
        template=project_template("mood"),
    )

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert (target_project / "code" / "library" / "survey" / "survey-mood.json").exists()
    assert not (primary_project / "code" / "library" / "survey" / "survey-mood.json").exists()


def test_template_editor_delete_can_target_explicit_project_path(tmp_path, monkeypatch):
    app, handlers = _build_app_and_handlers()

    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    primary_project.mkdir()
    target_project.mkdir()

    primary_file = primary_project / "code" / "library" / "survey" / "survey-mood.json"
    primary_file.parent.mkdir(parents=True)
    primary_file.write_text('{"project": "primary"}', encoding="utf-8")

    target_file = target_project / "code" / "library" / "survey" / "survey-mood.json"
    target_file.parent.mkdir(parents=True)
    target_file.write_text('{"project": "target"}', encoding="utf-8")

    with app.test_request_context(
        "/api/template-editor/delete",
        method="DELETE",
        json={
            "modality": "survey",
            "filename": "survey-mood.json",
            "project_path": str(target_project),
        },
    ):
        session["current_project_path"] = str(primary_project)
        response, status_code = handlers.api_template_editor_delete()

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert primary_file.exists()
    assert not target_file.exists()


def test_template_editor_list_merged_can_target_explicit_project_path(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    primary_project.mkdir()
    target_project.mkdir()

    primary_file = (
        primary_project / "code" / "library" / "survey" / "survey-primary.json"
    )
    primary_file.parent.mkdir(parents=True)
    primary_file.write_text("{}", encoding="utf-8")

    target_file = target_project / "code" / "library" / "survey" / "survey-target.json"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(handlers, "_global_survey_library_root", lambda: None)
    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    monkeypatch.setattr(handlers, "_validate_against_schema", lambda **kwargs: [])
    monkeypatch.setattr(
        handlers,
        "load_config",
        lambda _path: SimpleNamespace(template_library_path=None),
    )

    with app.test_request_context(
        "/api/template-editor/list-merged",
        method="GET",
        query_string={
            "modality": "survey",
            "schema_version": "stable",
            "project_path": str(target_project),
        },
    ):
        session["current_project_path"] = str(primary_project)
        response, status_code = handlers.api_template_editor_list_merged()

    assert status_code == 200
    payload = response.get_json()
    filenames = [entry["filename"] for entry in payload["templates"]]
    assert "survey-target.json" in filenames
    assert "survey-primary.json" not in filenames
    assert payload["sources"]["project_library_path"] == str(
        target_project / "code" / "library"
    )
    assert payload["has_project"] is True


def test_global_survey_library_root_prefers_configured_path_over_builtin(
    tmp_path, monkeypatch
):
    import src.config as config

    app, _ = _build_app_and_handlers()
    helpers = importlib.import_module("src.web.blueprints.tools_helpers")

    custom = tmp_path / "custom_library"
    (custom / "survey").mkdir(parents=True)
    monkeypatch.setattr(
        config,
        "load_app_settings",
        lambda app_root=None: config.AppSettings(
            global_template_library_path=str(custom)
        ),
    )

    with app.test_request_context():
        assert helpers._global_survey_library_root() == custom.resolve()
