"""The editor's template list marks a library template valid by the same rule the save and the gate use:
the file name is the task name, so an official template without Study.TaskName is not a red cross."""

import importlib
import json
import os
import sys
from pathlib import Path

from flask import Flask, session

from tests.template_fixtures import library_template

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _list(tmp_path, monkeypatch, templates):
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    library = tmp_path / "library"
    (library / "survey").mkdir(parents=True)
    for name, template in templates.items():
        (library / "survey" / name).write_text(json.dumps(template), encoding="utf-8")
    monkeypatch.setattr(handlers, "_global_survey_library_root", lambda: library)
    app = Flask(__name__, root_path=str(APP_ROOT))
    app.secret_key = os.urandom(32)
    with app.test_request_context("/api/template-editor/list-merged", query_string={"modality": "survey", "schema_version": "stable"}):
        session["current_project_path"] = str(tmp_path / "proj")
        response, _ = handlers.api_template_editor_list_merged()
    return {t["filename"]: t for t in response.get_json()["templates"]}


def test_an_official_template_without_task_name_is_valid_in_the_list(tmp_path, monkeypatch):
    official = library_template()
    official["Study"].pop("TaskName")

    listed = _list(tmp_path, monkeypatch, {"survey-gad7.json": official})

    assert listed["survey-gad7.json"]["template_valid"] is True, listed["survey-gad7.json"]


def test_no_official_template_is_a_red_cross_in_the_list(tmp_path, monkeypatch):
    official = Path(__file__).resolve().parents[1] / "official" / "library" / "survey"
    templates = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in official.glob("survey-*.json")}

    listed = _list(tmp_path, monkeypatch, templates)

    red = {name: t["validation_error"] for name, t in listed.items() if t["template_valid"] is not True}
    assert not red, red


def test_a_template_that_really_lacks_a_global_field_is_still_marked(tmp_path, monkeypatch):
    broken = library_template()
    broken["Study"].pop("Citation")

    listed = _list(tmp_path, monkeypatch, {"survey-gad7.json": broken})

    assert listed["survey-gad7.json"]["template_valid"] is False
    assert "Citation" in listed["survey-gad7.json"]["validation_error"]
