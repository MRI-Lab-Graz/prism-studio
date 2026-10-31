"""Warnings reach the user: in Studio's Validate answer and in `library template-check`, from one backend function,
and a language check that cannot run is said so, never silently skipped."""

import copy
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask

from tests.template_fixtures import project_template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from src.template_save import template_warnings  # noqa: E402
from src.template_validator import TemplateValidator  # noqa: E402


def _with_missing_french() -> dict:
    template = copy.deepcopy(project_template("warn"))
    template["I18n"]["Languages"] = ["en", "de", "fr"]  # GAD-7 has no French text: a warning, not an error
    return template


def test_a_clean_template_has_no_warnings():
    assert template_warnings(project_template("warn")) == ([], [])


def test_template_warnings_lists_language_and_item_warnings():
    template = _with_missing_french()
    template["bad id!"] = copy.deepcopy(template["GAD701"])
    language, items = template_warnings(template)

    assert any("'fr'" in w["message"] for w in language)
    assert any("bad id!" in w["path"] for w in items)
    assert all(w["severity"] == "warning" for w in items)


def test_a_check_that_cannot_run_is_reported_not_swallowed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(TemplateValidator, "validate_language_consistency_from_data", staticmethod(boom))
    language, _ = template_warnings(project_template("warn"))

    assert any("could not run" in w["message"] and "kaboom" in w["message"] for w in language)


def test_studio_validate_returns_the_same_warnings():
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(handlers.tools_template_editor_bp)
    template = _with_missing_french()

    body = app.test_client().post(
        "/api/template-editor/validate", json={"modality": "survey", "template": template}
    ).get_json()
    language, items = template_warnings(template)

    assert body["language_warnings"] and [w["message"] for w in body["language_warnings"]] == [w["message"] for w in language]
    assert body["item_warnings"] == items


def test_the_cli_prints_the_warnings_and_still_exits_zero(tmp_path):
    folder = tmp_path / "code" / "library" / "survey"
    folder.mkdir(parents=True)
    (folder / "survey-warn.json").write_text(json.dumps(_with_missing_french()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "app" / "prism_tools.py"), "library", "template-check", "--project", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Warning" in result.stdout and "'fr'" in result.stdout


def test_the_validate_panel_escapes_warning_text_from_the_template():
    # item ids and language keys come from the template file, which travels between projects
    script = (ROOT / "app" / "static" / "js" / "template-editor" / "source-workflow.js").read_text(encoding="utf-8")
    assert "context.escapeHtml(warning.message)" in script
    assert "${warning.message}" not in script
