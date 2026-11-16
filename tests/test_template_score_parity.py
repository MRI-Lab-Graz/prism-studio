"""`library template-score` and the editor's completeness route run one function: same template, same numbers."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask

from src.template_completeness import template_completeness
from tests.template_fixtures import project_template

ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = ROOT / "app"


def _incomplete():
    template = project_template()
    template["Technical"].pop("Respondent")
    template["Study"].pop("DOI", None)
    return template


def _cli(tmp_path, template, *extra):
    path = tmp_path / "survey-x.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(APP_ROOT / "prism_tools.py"), "library", "template-score", "--template", str(path), *extra],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=120,
    )


def _route(template, **extra):
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(APP_ROOT))
    app.secret_key = os.urandom(32)
    with app.test_request_context(
        "/api/template-editor/completeness", method="POST",
        json={"template": template, "filename": "survey-x.json", **extra},
    ):
        response = handlers.api_template_editor_completeness()
    return response.get_json()


def test_the_command_prints_what_the_function_computes(tmp_path):
    template = _incomplete()

    result = _cli(tmp_path, template, "--json")

    assert result.returncode == 1  # not complete, like template-check
    assert json.loads(result.stdout) == template_completeness(template, source=str(tmp_path / "survey-x.json"))


def test_the_command_in_words_names_the_missing_fields(tmp_path):
    result = _cli(tmp_path, _incomplete())

    assert "Technical/Respondent" in result.stdout
    assert "Required" in result.stdout and "Recommended" in result.stdout


def test_a_complete_template_exits_zero(tmp_path):
    assert _cli(tmp_path, project_template()).returncode == 0


def test_the_route_returns_the_same_numbers_as_the_command(tmp_path):
    template = _incomplete()

    from_cli = json.loads(_cli(tmp_path, template, "--json").stdout)

    assert _route(template) == from_cli


def test_the_route_and_the_command_agree_on_a_library_template(tmp_path):
    template = _incomplete()

    from_cli = json.loads(_cli(tmp_path, template, "--json", "--is-global").stdout)

    assert _route(template, is_global=True) == from_cli
    assert from_cli["complete"] is True


def test_the_route_and_the_command_carry_the_same_prism_id(tmp_path):
    template = project_template()
    template["Study"]["TaskName"] = "demo"

    from_cli = json.loads(_cli(tmp_path, template, "--json").stdout)

    assert from_cli["prism_id"] == _route(template)["prism_id"] == "prism:demo"


def test_no_prism_id_without_a_task_name(tmp_path):
    template = project_template()
    template["Study"].pop("TaskName")

    assert json.loads(_cli(tmp_path, template, "--json").stdout)["prism_id"] is None


# --- project-level fields of a library template are open, not missing and not filled ---------------------------

PROJECT_ONLY = ["Technical/Respondent", "Technical/AdministrationMethod", "Technical/SoftwarePlatform"]


def _library():
    from tests.template_fixtures import library_template

    template = library_template()
    for field in ("Respondent", "AdministrationMethod", "SoftwarePlatform", "SoftwareVersion"):
        template["Technical"].pop(field, None)
    return template


def test_a_library_template_lists_its_open_project_fields_and_does_not_count_them():
    result = template_completeness(_library(), source="survey-x.json", project=False)

    assert result["project_only"]["total"] == 3 and result["project_only"]["filled"] == 0
    assert sorted(result["project_only"]["open"]) == sorted(PROJECT_ONLY)
    assert not set(PROJECT_ONLY) & set(result["required"]["missing"])
    with_all = template_completeness(project_template(), source="survey-x.json", project=False)
    assert result["required"]["total"] == with_all["required"]["total"]  # project fields are never in required.*
    assert result["percent"]["required"] == 100


def test_a_filled_project_field_of_a_library_template_is_reported_under_project_only():
    template = _library()
    template["Technical"]["Respondent"] = "self"

    result = template_completeness(template, source="survey-x.json", project=False)

    assert result["project_only"]["filled"] == 1
    assert "Technical/Respondent" not in result["project_only"]["open"]
    unfilled = template_completeness(_library(), source="survey-x.json", project=False)
    assert result["required"] == unfilled["required"]  # filled or open, required.* does not move


def test_a_project_template_has_no_open_project_fields():
    result = template_completeness(_incomplete(), source="survey-x.json", project=True)

    assert "project_only" not in result
    assert "Technical/Respondent" in result["required"]["missing"]


def test_the_route_and_the_command_agree_on_the_open_project_fields(tmp_path):
    template = _library()

    from_cli = json.loads(_cli(tmp_path, template, "--json", "--is-global").stdout)

    assert _route(template, is_global=True) == from_cli
    assert sorted(from_cli["project_only"]["open"]) == sorted(PROJECT_ONLY)


def test_a_project_template_result_has_exactly_the_keys_it_always_had():
    result = template_completeness(project_template(), source="survey-x.json", project=True)

    assert set(result) == {"required", "recommended", "problems", "prism_id", "complete", "percent"}
    assert set(result["required"]) == {"total", "filled", "missing"}


def test_the_command_in_words_prints_the_project_fields(tmp_path):
    result = _cli(tmp_path, _library(), "--is-global")

    assert "Project" in result.stdout and "Technical/Respondent" in result.stdout
