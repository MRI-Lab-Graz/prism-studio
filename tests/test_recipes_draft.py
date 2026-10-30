"""Recipe builder analysis as commands: `recipes templates|draft|load` run what Studio's builder endpoints run (THE RULE, CLAUDE.md)."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src import recipe_builder as rb  # noqa: E402

TEMPLATE = {
    "Technical": {"Language": "en"},
    "Study": {"Name": "ADS"},
    "Questions": {
        "ADS01": {"Description": {"en": "I felt sad."}, "Reversed": True, "MinValue": 0, "MaxValue": 3},
        "ADS02": {"Description": "Sleep.", "Levels": {"0": {"en": "Never"}, "1": {"en": "Sometimes"}}},
        "ADS03": {"Description": "Range is missing."},
        "ADS04": {"Description": "Excluded.", "_exclude": True, "MinValue": 0, "MaxValue": 3},
    },
}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "study"
    library = root / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-ads.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    return root


def _client():
    handlers = importlib.import_module("src.web.blueprints.tools")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.register_blueprint(handlers.tools_bp)
    return app.test_client()


def _args(project, **kw):
    return SimpleNamespace(project=str(project), modality="survey", include_global=False, task="ads", json=True, **kw)


def test_the_draft_is_the_analysis_of_the_template(project):
    draft = rb.draft_from_template(project, "ads", modality="survey")
    assert draft["items"] == ["ADS01", "ADS02", "ADS03"]
    assert draft["template_reversed_items"] == ["ADS01"]
    assert draft["items_missing_ranges"] == ["ADS03"]


def test_an_unknown_task_gives_an_empty_draft(project):
    assert rb.draft_from_template(project, "nope") == {"items": []}


def test_the_template_list_has_the_fields_the_builder_shows(project):
    surveys = rb.list_builder_templates(project)
    assert [(s["task"], s["source"]) for s in surveys] == [("ads", "project")] and set(surveys[0]) == {"task", "label", "file", "source"}


def test_load_returns_none_without_a_recipe_and_refuses_a_task_with_a_path(project):
    assert rb.load_recipe(project, "ads") is None
    with pytest.raises(rb.RecipeSaveError):
        rb.load_recipe(project, "../x")


def test_the_commands_print_what_studios_endpoints_return(project, capsys):
    import src.cli.commands.recipes as commands

    (project / "code" / "recipes" / "survey").mkdir(parents=True)
    (project / "code" / "recipes" / "survey" / "recipe-ads.json").write_text(json.dumps({"Kind": "survey"}), encoding="utf-8")
    client = _client()
    params = {"dataset_path": str(project), "task": "ads"}
    for command, route in (
        (commands.cmd_recipes_templates, "/api/recipe-builder/surveys"),
        (commands.cmd_recipes_draft, "/api/recipe-builder/items"),
        (commands.cmd_recipes_load, "/api/recipe-builder/load"),
    ):
        command(_args(project))
        cli = json.loads(capsys.readouterr().out)
        studio = client.get(route, query_string=params).get_json()
        studio.pop("path", None), cli.pop("path", None)
        assert cli == studio, route


def test_save_and_the_builder_use_the_same_global_library(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(rb, "save_recipe_to_project", lambda *a, **k: seen.append(k["global_root"]) or {"path": "x"})
    import src.cli.commands.recipes as commands

    monkeypatch.setattr(commands, "global_survey_library_root", lambda: tmp_path)
    commands.cmd_recipes_save(SimpleNamespace(project=str(tmp_path), recipe=str(_recipe_file(tmp_path)), modality="survey", json=True))
    assert seen == [tmp_path]


def _recipe_file(tmp_path):
    path = tmp_path / "r.json"
    path.write_text("{}", encoding="utf-8")
    return path
