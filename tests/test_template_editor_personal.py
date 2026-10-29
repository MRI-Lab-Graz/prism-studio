"""The template editor lists and saves into the personal library."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, session

from src import config


@pytest.fixture
def editor(tmp_path, monkeypatch):
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)

    mine = tmp_path / "mine"
    (mine / "survey").mkdir(parents=True)
    (mine / "survey" / "survey-mine.json").write_text('{"Study": {"TaskName": "mine"}}', encoding="utf-8")
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings(personal_library_path=str(mine)))
    monkeypatch.setattr(handlers, "_global_survey_library_root", lambda: None)
    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    monkeypatch.setattr(handlers, "_validate_against_schema", lambda **kwargs: [])
    monkeypatch.setattr(handlers, "load_config", lambda _path: SimpleNamespace(template_library_path=None))
    project = tmp_path / "proj"
    project.mkdir()
    return app, handlers, mine, project


def test_list_shows_personal_templates_under_their_own_source(editor):
    app, handlers, mine, project = editor
    with app.test_request_context("/api/template-editor/list-merged", query_string={"modality": "survey", "schema_version": "stable"}):
        session["current_project_path"] = str(project)
        response, status = handlers.api_template_editor_list_merged()

    assert status == 200
    payload = response.get_json()
    entry = next(t for t in payload["templates"] if t["filename"] == "survey-mine.json")
    assert entry["source"] == "personal" and entry["readonly"] is False
    assert payload["has_personal"] is True


def test_the_project_template_wins_over_a_personal_one_of_the_same_name(editor):
    app, handlers, mine, project = editor
    (project / "code" / "library" / "survey").mkdir(parents=True)
    (project / "code" / "library" / "survey" / "survey-mine.json").write_text("{}", encoding="utf-8")
    with app.test_request_context("/api/template-editor/list-merged", query_string={"modality": "survey", "schema_version": "stable"}):
        session["current_project_path"] = str(project)
        response, _ = handlers.api_template_editor_list_merged()

    sources = [t["source"] for t in response.get_json()["templates"] if t["filename"] == "survey-mine.json"]
    assert sources == ["project"]


def _save(app, handlers, project, **extra):
    with app.test_request_context(
        "/api/template-editor/save", method="POST",
        json={"modality": "survey", "schema_version": "stable", "filename": "survey-new.json",
              "template": {"Study": {"TaskName": "new"}}, **extra},
    ):
        session["current_project_path"] = str(project)
        return handlers.api_template_editor_save()


def test_save_to_the_personal_library_leaves_the_project_alone(editor):
    app, handlers, mine, project = editor
    response, status = _save(app, handlers, project, target="personal")

    assert status == 200
    assert json.loads((mine / "survey" / "survey-new.json").read_text(encoding="utf-8"))["Study"]["TaskName"] == "new"
    assert not (project / "code").exists()


def test_save_to_a_personal_library_that_is_not_set_says_how_to_set_it(editor, monkeypatch):
    app, handlers, mine, project = editor
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings())
    response, status = _save(app, handlers, project, target="personal")

    assert status == 400
    assert "Personal Template Library" in response.get_json()["error"]
