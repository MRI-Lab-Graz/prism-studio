"""Columns of the project's participants.tsv are variables a recipe may use."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.recipes import cmd_recipes_validate_file  # noqa: E402
from src.recipe_builder import draft_from_template, save_recipe_to_project  # noqa: E402
from src.recipe_validation import validate_recipe  # noqa: E402
from src.recipes_surveys import compute_survey_recipes  # noqa: E402

RECIPE = {
    "RecipeVersion": "1.0",
    "Kind": "survey",
    "Survey": {"TaskName": "demo"},
    "Scores": [
        {"Name": "adj", "Method": "formula", "Items": ["q1", "age"], "Formula": "{q1}+{age}"}
    ],
}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "participants.tsv").write_text(
        "participant_id\tage\tq2\nsub-01\t30\t99\n", encoding="utf-8"
    )
    template = {
        "Technical": {},
        "Study": {"TaskName": "demo"},
        "q1": {"Description": "one"},
        "q2": {"Description": "two"},
    }
    lib = tmp_path / "code" / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-demo.json").write_text(json.dumps(template), encoding="utf-8")
    data = tmp_path / "sub-01" / "ses-1" / "survey"
    data.mkdir(parents=True)
    (data / "sub-01_ses-1_task-demo_survey.tsv").write_text("q1\tq2\n2\tn/a\n", encoding="utf-8")
    return tmp_path


def _recipe_file(project, recipe=RECIPE):
    folder = project / "code" / "recipes" / "survey"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "recipe-demo.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return path


def _score(project):
    result = compute_survey_recipes(
        prism_root=project, repo_root=APP_ROOT.parent, out_format="csv"
    )
    return next(result.out_root.glob("*demo.csv")).read_text(encoding="utf-8").splitlines()


def test_draft_lists_participant_variables_that_are_not_items(project):
    draft = draft_from_template(project, "demo")

    assert draft["participant_variables"] == ["age"]  # q2 is an item, so the item wins


def test_save_accepts_a_participant_variable(project):
    assert save_recipe_to_project(str(project), RECIPE)["saved"]


def test_a_variable_the_project_does_not_have_is_named(project):
    (project / "participants.tsv").write_text("participant_id\tsex\nsub-01\tF\n", encoding="utf-8")

    errors = validate_recipe(RECIPE, known_items={"q1"}, participant_variables=["sex"])

    assert "['age']" in errors[0] and "participants.tsv" in errors[0]


def test_participant_variables_cannot_be_reverse_scored():
    recipe = {**RECIPE, "Transforms": {"Invert": {"Items": ["age"], "Scale": {"min": 1, "max": 5}}}}

    errors = validate_recipe(recipe, known_items={"q1"}, participant_variables=["age"])

    assert any("Invert.Items" in e for e in errors)


def test_validate_file_takes_a_project(project, capsys):
    template = project / "code" / "library" / "survey" / "survey-demo.json"
    cmd_recipes_validate_file(
        SimpleNamespace(
            recipe=str(_recipe_file(project)),
            known_items_from=str(template),
            project=str(project),
            recipe_id=None,
            json=False,
        )
    )

    assert "valid recipe" in capsys.readouterr().out


def test_scoring_uses_the_participant_value(project):
    _recipe_file(project)

    header, row = _score(project)[:2]

    assert dict(zip(header.split(","), row.split(",")))["adj"] == "32"


def test_an_unanswered_item_is_not_filled_from_participants(project):
    _recipe_file(
        project,
        {**RECIPE, "Scores": [{"Name": "adj", "Method": "sum", "Items": ["q2"]}]},
    )

    header, row = _score(project)[:2]

    assert dict(zip(header.split(","), row.split(",")))["adj"] == ""  # missing
