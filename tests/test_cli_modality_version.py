import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.modality_version as cmds  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "project.json").write_text(json.dumps({"Metadata": {"SchemaVersion": "1.0.0"}}))
    survey = tmp_path / "sub-01" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_task-a_survey.tsv").write_text("x")
    return tmp_path


def _args(project, **over):
    values = dict(project=str(project), names=[], name=None, json=False)
    values.update(over)
    return SimpleNamespace(**values)


def test_parser_accepts_the_commands():
    parser, parsers = build_prism_tools_parsers(APP_ROOT)
    a = parser.parse_args(["modality-version", "update", "/p", "survey"])
    assert (a.command, a.action, a.project, a.name) == ("modality-version", "update", "/p", "survey")
    a = parser.parse_args(["modality-version", "pin", "/p", "survey", "physio"])
    assert a.names == ["survey", "physio"]
    assert "modality-version" in parsers


def test_pin_with_no_names_pins_what_is_present(project, capsys):
    cmds.cmd_modality_version_pin(_args(project, json=True))
    out = json.loads(capsys.readouterr().out)
    assert out["success"] and "survey" in out["pinned"]
    assert "survey" in json.loads((project / "project.json").read_text())["SchemaVersions"]


def test_status_lists_pins_and_pending(project, capsys):
    cmds.cmd_modality_version_pin(_args(project))
    capsys.readouterr()
    cmds.cmd_modality_version_status(_args(project, json=True))
    out = json.loads(capsys.readouterr().out)
    assert out["success"] and "survey" in out["pins"] and out["pending"] == []


def test_update_unpinned_modality_exits_1_with_json_error(project, capsys):
    with pytest.raises(SystemExit) as exc:
        cmds.cmd_modality_version_update(_args(project, name="survey", json=True))
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["success"] is False


def test_list_shows_versions_of_a_modality(capsys):
    cmds.cmd_modality_version_list(SimpleNamespace(name="survey", json=False))
    assert "survey" in capsys.readouterr().out


def test_unknown_modality_in_list_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        cmds.cmd_modality_version_list(SimpleNamespace(name="nope", json=True))
    assert exc.value.code == 1


@pytest.mark.parametrize("fn,extra", [
    (cmds.cmd_modality_version_status, {}),
    (cmds.cmd_modality_version_pin, {}),
    (cmds.cmd_modality_version_pin, {"names": ["survey"]}),
    (cmds.cmd_modality_version_update, {"name": "survey"}),
    (cmds.cmd_modality_version_freeze, {"name": "survey"}),
])
@pytest.mark.parametrize("where", ["missing", "no_project_json"])
def test_non_project_path_exits_1_with_project_json_error(fn, extra, where, tmp_path, capsys):
    path = tmp_path / "nope" if where == "missing" else tmp_path
    with pytest.raises(SystemExit) as exc:
        fn(_args(path, json=True, **extra))
    assert exc.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is False and "project.json" in out["error"]


@pytest.mark.parametrize("bad", ["dataset_description", "project", "../stable/biometrics", "nope"])
def test_cli_pin_rejects_non_modality_names(project, capsys, bad):
    with pytest.raises(SystemExit) as exc:
        cmds.cmd_modality_version_pin(_args(project, names=[bad], json=True))
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["success"] is False
    assert "SchemaVersions" not in json.loads((project / "project.json").read_text())


@pytest.mark.parametrize("fn", ["pin", "update", "freeze"])
def test_read_only_project_exits_1_not_traceback(project, capsys, monkeypatch, fn):
    cmds.cmd_modality_version_pin(_args(project, names=["survey"]))
    capsys.readouterr()

    def boom(*a, **k):
        raise PermissionError("read-only")

    monkeypatch.setattr("src.modality_versions._write_pins", boom)
    args = _args(project, names=["biometrics"], name="survey", json=True)
    with pytest.raises(SystemExit) as exc:
        getattr(cmds, f"cmd_modality_version_{fn}")(args)
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["success"] is False
