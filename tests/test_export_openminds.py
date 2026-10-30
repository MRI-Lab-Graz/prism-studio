"""openMINDS export: the run, the description patch and the task list are backend code; command and route agree."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src import export_openminds as eom  # noqa: E402


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "study"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"TaskDefinitions": {"stroop": {}, "nback": {}}}), encoding="utf-8")
    return root


def _fake_run(commands, returncode=0, stderr=""):
    def run(cmd, **kwargs):
        commands.append(cmd)
        output = Path(cmd[cmd.index("-o") + 1])
        if returncode == 0 and output.suffix == ".jsonld":
            output.write_text(json.dumps({"@graph": [{"https://x/name": "stroop", "https://x/description": "To be defined"}]}), encoding="utf-8")
        return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)

    return run


def test_the_tasks_are_the_projects_task_definitions(project, tmp_path):
    assert eom.openminds_tasks(project) == ["nback", "stroop"]
    (tmp_path / "empty").mkdir()
    assert eom.openminds_tasks(tmp_path / "empty") == []


def test_the_export_runs_the_tool_on_the_project_and_patches_protocol_descriptions(project):
    commands = []
    with patch.object(eom, "find_bids2openminds", lambda: "/bin/bids2openminds"), patch("subprocess.run", _fake_run(commands)):
        result = eom.run_openminds_export(project, {"supplements": {"protocol_descriptions": {"stroop": " Read the colour. "}, "ethics_category": "low risk"}})

    out = project.parent / "study_openminds.jsonld"
    assert commands[0][:4] == ["/bin/bids2openminds", str(project), "-o", str(out)] and "--single-file" in commands[0]
    assert json.loads(out.read_text(encoding="utf-8"))["@graph"][0]["https://x/description"] == "Read the colour."
    assert result["has_notes"] and json.loads((project.parent / "study_openminds_supplements.json").read_text(encoding="utf-8")) == {"ethics_assessment": "low risk"}


def test_multiple_files_and_empty_properties_are_passed_to_the_tool(project):
    commands = []
    with patch.object(eom, "find_bids2openminds", lambda: "/bin/b"), patch("subprocess.run", _fake_run(commands)):
        eom.run_openminds_export(project, {"single_file": False, "include_empty": True})
    assert "--multiple-files" in commands[0] and "--include-empty-properties" in commands[0]
    assert commands[0][commands[0].index("-o") + 1] == str(project.parent / "study_openminds")


def test_a_missing_tool_and_a_failing_tool_are_reported_with_the_reason(project):
    with patch.object(eom, "find_bids2openminds", lambda: None):
        with pytest.raises(eom.OpenMindsError, match="pip install bids2openminds"):
            eom.run_openminds_export(project, {})
    with patch.object(eom, "find_bids2openminds", lambda: "/bin/b"), patch("subprocess.run", _fake_run([], returncode=1, stderr="bad dataset")):
        with pytest.raises(eom.OpenMindsError, match="bad dataset"):
            eom.run_openminds_export(project, {})


def test_the_command_and_studios_route_give_the_same_result(project, capsys):
    import src.cli.commands.export as export_commands

    args = SimpleNamespace(project=str(project), multiple_files=False, include_empty=False, protocol_description=["stroop=Read the colour."], ethics_category="low risk", json=True)
    with patch.object(eom, "find_bids2openminds", lambda: "/bin/b"), patch("subprocess.run", _fake_run([])):
        export_commands.cmd_export_openminds(args)
        cli = json.loads(capsys.readouterr().out)
        blueprint = importlib.import_module("src.web.blueprints.projects_export_blueprint")
        app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
        app.register_blueprint(blueprint.projects_export_bp)
        studio = app.test_client().post("/api/projects/openminds-export", json={
            "project_path": str(project), "supplements": {"protocol_descriptions": {"stroop": "Read the colour."}, "ethics_category": "low risk"},
        }).get_json()
    assert cli == studio and cli["success"] is True
