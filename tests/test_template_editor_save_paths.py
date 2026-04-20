from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, session


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


def test_template_editor_save_relaxes_schema_when_copying_global_template(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    captured_required = {}

    def _fake_validate_against_schema(*, instance, schema):
        captured_required["study"] = list(
            schema.get("properties", {}).get("Study", {}).get("required", [])
        )
        captured_required["technical"] = list(
            schema.get("properties", {}).get("Technical", {}).get("required", [])
        )
        return []

    monkeypatch.setattr(
        handlers,
        "_load_prism_schema",
        lambda **kwargs: {
            "properties": {
                "Study": {"required": ["TaskName", "LicenseID", "Citation"]},
                "Technical": {"required": ["SoftwarePlatform", "AdministrationMethod"]},
            }
        },
    )
    monkeypatch.setattr(
        handlers, "_validate_against_schema", _fake_validate_against_schema
    )

    template = {
        "Study": {"ShortName": "aai"},
        "Technical": {"Language": "en"},
    }

    with app.test_request_context(
        "/api/template-editor/save",
        method="POST",
        json={
            "modality": "survey",
            "schema_version": "stable",
            "filename": "survey-aai.json",
            "is_global": True,
            "template": template,
        },
    ):
        session["current_project_path"] = str(tmp_path)
        response, status_code = handlers.api_template_editor_save()

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert "TaskName" not in captured_required["study"]
    assert "LicenseID" not in captured_required["study"]
    assert "Citation" not in captured_required["study"]
    assert "SoftwarePlatform" not in captured_required["technical"]
    assert "AdministrationMethod" not in captured_required["technical"]


def test_template_editor_save_is_strict_when_not_copying_global_template(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    def _fake_validate_against_schema(*, instance, schema):
        required_study = (
            schema.get("properties", {}).get("Study", {}).get("required", [])
        )
        if "TaskName" in required_study and "TaskName" not in instance.get("Study", {}):
            return [{"path": "$.Study", "message": "'TaskName' is a required property"}]
        return []

    monkeypatch.setattr(
        handlers,
        "_load_prism_schema",
        lambda **kwargs: {
            "properties": {
                "Study": {"required": ["TaskName"]},
                "Technical": {"required": []},
            }
        },
    )
    monkeypatch.setattr(
        handlers, "_validate_against_schema", _fake_validate_against_schema
    )

    template = {
        "Study": {"ShortName": "aai"},
        "Technical": {"Language": "en"},
    }

    with app.test_request_context(
        "/api/template-editor/save",
        method="POST",
        json={
            "modality": "survey",
            "schema_version": "stable",
            "filename": "survey-aai.json",
            "template": template,
        },
    ):
        session["current_project_path"] = str(tmp_path)
        response, status_code = handlers.api_template_editor_save()

    assert status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Template validation failed"
    assert payload["errors"]


def test_template_editor_save_requires_explicit_overwrite_confirmation(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    monkeypatch.setattr(handlers, "_validate_against_schema", lambda **kwargs: [])

    existing_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text('{"status": "original"}', encoding="utf-8")

    template = {
        "Study": {"TaskName": "mood", "ShortName": "mood"},
        "Technical": {"Language": "en"},
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

    assert status_code == 409
    payload = response.get_json()
    assert (
        payload["error"]
        == 'Template "survey-mood.json" already exists in the project library'
    )
    assert payload["code"] == "file_exists"
    assert json.loads(existing_path.read_text(encoding="utf-8")) == {
        "status": "original"
    }


def test_template_editor_save_allows_confirmed_overwrite(tmp_path, monkeypatch):
    app, handlers = _build_app_and_handlers()

    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    monkeypatch.setattr(handlers, "_validate_against_schema", lambda **kwargs: [])

    existing_path = tmp_path / "code" / "library" / "survey" / "survey-mood.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text('{"status": "original"}', encoding="utf-8")

    template = {
        "Study": {"TaskName": "mood", "ShortName": "mood"},
        "Technical": {"Language": "en"},
        "MOOD01": {"Description": "I feel calm."},
    }

    with app.test_request_context(
        "/api/template-editor/save",
        method="POST",
        json={
            "modality": "survey",
            "schema_version": "stable",
            "filename": "survey-mood.json",
            "allow_overwrite": True,
            "template": template,
        },
    ):
        session["current_project_path"] = str(tmp_path)
        response, status_code = handlers.api_template_editor_save()

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert json.loads(existing_path.read_text(encoding="utf-8")) == template


def test_template_editor_save_can_target_explicit_project_path(tmp_path, monkeypatch):
    app, handlers = _build_app_and_handlers()

    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    primary_project.mkdir()
    target_project.mkdir()

    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    monkeypatch.setattr(handlers, "_validate_against_schema", lambda **kwargs: [])

    template = {
        "Study": {"TaskName": "mood", "ShortName": "mood"},
        "Technical": {"Language": "en"},
    }

    with app.test_request_context(
        "/api/template-editor/save",
        method="POST",
        json={
            "modality": "survey",
            "schema_version": "stable",
            "filename": "survey-mood.json",
            "project_path": str(target_project),
            "template": template,
        },
    ):
        session["current_project_path"] = str(primary_project)
        response, status_code = handlers.api_template_editor_save()

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert (
        target_project / "code" / "library" / "survey" / "survey-mood.json"
    ).exists()
    assert not (
        primary_project / "code" / "library" / "survey" / "survey-mood.json"
    ).exists()


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
