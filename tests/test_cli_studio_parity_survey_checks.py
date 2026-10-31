"""Studio's survey page asks two questions about an input table before converting: do the project's templates match and
are they complete (template check), and which task versions / sessions / runs does it hold (version contexts).
The CLI answers both from the same backend functions; these tests run the command and Studio's real route on twin
projects and compare the answers."""

import io
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_cli_studio_parity import world  # noqa: F401 - fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _twin(tmp_path, project):
    """The same project in a second folder of the same name (the paths in the answers differ only by the parent)."""
    twin = tmp_path / "studio_side" / project.name
    shutil.copytree(project, twin)
    return twin


def _studio_post(path, view_name, project, table, **fields):
    import importlib

    from flask import Flask

    handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
    app = Flask(__name__, root_path=str(APP_DIR))
    app.secret_key = "test"  # pragma: allowlist secret
    app.add_url_rule(path, view_func=getattr(handlers, view_name), methods=["POST"])
    data = {"project_path": str(project), "excel": (io.BytesIO(table.read_bytes()), table.name), **fields}
    response = app.test_client().post(path, data=data, content_type="multipart/form-data")
    return response.get_json(), response.status_code


def _same_but_for_the_folder(cli_payload, cli_project, studio_payload, studio_project):
    swap = lambda payload, root: json.loads(json.dumps(payload).replace(str(root), "<project>"))  # noqa: E731
    assert swap(cli_payload, cli_project) == swap(studio_payload, studio_project)


def test_the_template_check_answers_the_same_in_the_cli_and_in_studio(world, tmp_path, capsys):  # noqa: F811
    from src.cli.commands.library import cmd_library_template_check

    project, table = world
    twin = _twin(tmp_path, project)

    try:
        cmd_library_template_check(SimpleNamespace(
            project=str(project), tasks=None, schema_version="stable", input=str(table), id_column="ID",
            session_column=None, sheet="0", separator="auto", duplicate_handling="error", json=True,
        ))
    except SystemExit:
        pass  # exit 1 = templates incomplete: the answer is still printed
    cli = json.loads(capsys.readouterr().out)
    studio, status = _studio_post("/check", "api_survey_check_project_templates", twin, table, id_column="ID")

    assert status == 200 and cli["matching"]["input_file"] == "pss.csv"
    assert cli["matching"]["match_error"] is None and cli["matching"]["matched_tasks"] == ["pss"]  # the matching ran
    _same_but_for_the_folder(cli, project, studio, twin)


def test_the_template_check_without_a_table_answers_the_same_in_the_cli_and_in_studio(world, tmp_path, capsys):  # noqa: F811
    from src.cli.commands.library import cmd_library_template_check

    project, table = world
    twin = _twin(tmp_path, project)

    try:
        cmd_library_template_check(SimpleNamespace(
            project=str(project), tasks=None, schema_version="stable", input=None, id_column=None,
            session_column=None, sheet="0", separator="auto", duplicate_handling="error", json=True,
        ))
    except SystemExit:
        pass
    cli = json.loads(capsys.readouterr().out)
    from flask import Flask
    import importlib

    handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
    app = Flask(__name__, root_path=str(APP_DIR))
    app.add_url_rule("/check", view_func=handlers.api_survey_check_project_templates, methods=["POST"])
    studio = app.test_client().post("/check", data={"project_path": str(twin)}).get_json()

    assert cli["matching"]["input_file"] is None
    _same_but_for_the_folder(cli, project, studio, twin)


def test_detecting_version_contexts_answers_the_same_in_the_cli_and_in_studio(world, tmp_path, capsys):  # noqa: F811
    from src.cli.commands.survey import cmd_survey_detect_version_contexts

    project, table = world
    twin = _twin(tmp_path, project)

    cmd_survey_detect_version_contexts(SimpleNamespace(
        input=str(table), project=str(project), survey=None, id_column="ID", session_column=None, run_column=None,
        session=None, sheet="0", separator="auto", duplicate_handling="error", template_versions=None,
        value_offsets=None, allow_near_item_match=False, near_match_tasks=None, json=True,
    ))
    cli = json.loads(capsys.readouterr().out)
    studio, status = _studio_post(
        "/contexts", "api_survey_detect_version_context", twin, table, id_column="ID"
    )

    assert status == 200 and studio["ok"] is True and cli["ok"] is True
    assert cli["tasks_included"] == ["pss"]
    _same_but_for_the_folder(cli, project, studio, twin)


@pytest.mark.parametrize("view", ["api_survey_prepare_workflow", "api_survey_workflow_command"])
def test_preparing_the_workflow_reports_what_the_cli_detects(world, tmp_path, capsys, view):  # noqa: F811
    """Studio's "prepare" runs the same dry run and only reshapes its answer (the page reads those fields); the command
    prints the same facts."""
    from src.cli.commands.survey import cmd_survey_detect_version_contexts

    project, table = world
    twin = _twin(tmp_path, project)
    cmd_survey_detect_version_contexts(SimpleNamespace(
        input=str(table), project=str(project), survey=None, id_column="ID", session_column=None, run_column=None,
        session=None, sheet="0", separator="auto", duplicate_handling="error", template_versions=None,
        value_offsets=None, allow_near_item_match=False, near_match_tasks=None, json=True,
    ))
    cli = json.loads(capsys.readouterr().out)
    extra = {"workflow_command": "prepare"} if view == "api_survey_workflow_command" else {}
    studio, status = _studio_post("/prepare", view, twin, table, id_column="ID", **extra)

    assert status == 200 and studio["ok"] is True, studio
    for field in ("detected_sessions", "task_runs", "session_column", "run_column", "multivariant_tasks"):
        assert studio[field] == cli[field], field
    assert studio["tasks_included"] == cli["tasks_included"]
