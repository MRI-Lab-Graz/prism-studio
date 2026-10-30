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
