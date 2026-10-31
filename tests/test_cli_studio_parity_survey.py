"""Studio's "Save templates to project" and `library save-templates` write the same files and answer the same."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from tests.template_fixtures import project_template
from tests.test_cli_studio_parity import _two_projects

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def _templates():
    with_export_keys = project_template("mood")
    item = next(k for k, v in with_export_keys.items() if isinstance(v, dict) and "Description" in v)
    with_export_keys[item]["LimeSurvey"] = {"questionType": "L", "inputWidth": "30", "columnName": "q1"}
    return [
        {"filename": "survey-mood.json", "content": project_template("mood")},
        {"filename": "survey-export-keys", "content": with_export_keys},  # no .json: both add it
        {"filename": "survey-broken.json", "content": ["not", "an", "object"]},
        {"filename": "../escape.json", "content": project_template("mood")},
        {"filename": "", "content": {}},
    ]


def _tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()}


def _normalized(body, root):
    return json.loads(json.dumps(body).replace(str(root), "<root>"))


def _cli(project, source, capsys):
    from src.cli.commands.library import cmd_library_save_templates

    code = 0
    try:
        cmd_library_save_templates(SimpleNamespace(project=str(project), input=str(source), json=True))
    except SystemExit as exc:
        code = exc.code
    return code, json.loads(capsys.readouterr().out)


def _studio(project, templates):
    from src.web.blueprints.tools_post_conversion_handlers import handle_limesurvey_save_to_project

    with Flask(__name__).test_request_context(method="POST"):
        return handle_limesurvey_save_to_project(project_path=str(project), data={"templates": templates}).get_json()


def test_saving_templates_writes_the_same_files_and_answers_the_same_in_the_cli_and_in_studio(tmp_path, capsys):
    cli, studio = _two_projects(tmp_path)
    source = tmp_path / "templates.json"
    source.write_text(json.dumps({"templates": _templates()}), encoding="utf-8")

    code, cli_body = _cli(cli, source, capsys)
    studio_body = _studio(studio, _templates())

    assert studio_body["success"] and code == 0
    assert _normalized(cli_body, cli) == _normalized(studio_body, studio)
    assert _tree(cli) == _tree(studio)
    assert sorted(f["filename"] for f in studio_body["saved_files"]) == ["survey-export-keys.json", "survey-mood.json"]
    assert len(studio_body["errors"]) == 3  # not an object, a path in the filename, an empty filename
    saved = (studio / "code/library/survey/survey-export-keys.json").read_text(encoding="utf-8")
    assert "questionType" not in saved and "inputWidth" not in saved  # the export settings are stripped


def test_saving_nothing_valid_fails_the_same_way_in_the_cli_and_in_studio(tmp_path, capsys):
    cli, studio = _two_projects(tmp_path)
    broken = [{"filename": "survey-broken.json", "content": []}]
    source = tmp_path / "templates.json"
    source.write_text(json.dumps(broken), encoding="utf-8")

    code, cli_body = _cli(cli, source, capsys)
    studio_body = _studio(studio, broken)

    assert not studio_body["success"] and code == 1
    assert _normalized(cli_body, cli) == _normalized(studio_body, studio)
