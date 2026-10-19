import json
from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from src.cli.dispatch import dispatch_prism_tools


def _incomplete(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({"Basics": {"Name": "x"}}), encoding="utf-8")
    return str(tmp_path)


def _run(args, handlers):
    parsers = {"root": MagicMock(), "survey": MagicMock()}
    dispatch_prism_tools(args, parsers=parsers, handlers=handlers)


def test_tool_command_blocked_on_incomplete_project(tmp_path, capsys):
    h = {"survey_convert": MagicMock()}
    args = Namespace(command="survey", action="convert", project=_incomplete(tmp_path))
    with pytest.raises(SystemExit) as exc:
        _run(args, h)
    assert exc.value.code == 2
    assert "Timepoints" in capsys.readouterr().out
    h["survey_convert"].assert_not_called()


def test_session_map_is_exempt(tmp_path):
    h = {"session_map_show": MagicMock()}
    args = Namespace(command="session-map", action="show", project=_incomplete(tmp_path))
    _run(args, h)
    h["session_map_show"].assert_called_once()


def test_non_project_output_is_not_gated(tmp_path):
    h = {"survey_convert": MagicMock()}
    args = Namespace(command="survey", action="convert", project=None, output=str(tmp_path / "new"))
    _run(args, h)
    h["survey_convert"].assert_called_once()


def test_complete_project_runs(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({
        "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    h = {"survey_convert": MagicMock()}
    _run(Namespace(command="survey", action="convert", project=str(tmp_path)), h)
    h["survey_convert"].assert_called_once()


def test_project_json_file_path_is_gated(tmp_path, capsys):
    _incomplete(tmp_path)
    h = {"survey_convert": MagicMock()}
    args = Namespace(command="survey", action="convert", project=str(tmp_path / "project.json"))
    with pytest.raises(SystemExit) as exc:
        _run(args, h)
    assert exc.value.code == 2
    h["survey_convert"].assert_not_called()


def test_project_json_file_path_complete_runs(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({
        "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    h = {"survey_convert": MagicMock()}
    _run(Namespace(command="survey", action="convert", project=str(tmp_path / "project.json")), h)
    h["survey_convert"].assert_called_once()


def test_environment_and_demo_are_exempt(tmp_path):
    p = _incomplete(tmp_path)
    h = {"environment_preview": MagicMock(), "demo_create": MagicMock()}
    _run(Namespace(command="environment", action="preview", project=p), h)
    _run(Namespace(command="demo", action="create", project=p), h)
    h["environment_preview"].assert_called_once()
    h["demo_create"].assert_called_once()


def test_save_gate_is_exempt(tmp_path):
    h = {"save_gate": MagicMock()}
    _run(Namespace(command="save-gate", project=_incomplete(tmp_path)), h)
    h["save_gate"].assert_called_once()


def test_datalad_doctor_is_a_diagnostic_and_is_exempt(tmp_path):
    h = {"datalad_doctor": MagicMock()}
    parsers = {"root": MagicMock(), "datalad": MagicMock()}
    args = Namespace(command="datalad", action="doctor", project=_incomplete(tmp_path))
    dispatch_prism_tools(args, parsers=parsers, handlers=h)
    h["datalad_doctor"].assert_called_once()


def test_recipes_prism_argument_names_a_project_and_is_gated(tmp_path):
    h = {"recipes_surveys": MagicMock()}
    parsers = {"root": MagicMock(), "recipes": MagicMock()}
    args = Namespace(command="recipes", action="surveys", prism=_incomplete(tmp_path))
    with pytest.raises(SystemExit) as exc:
        dispatch_prism_tools(args, parsers=parsers, handlers=h)
    assert exc.value.code == 2
    h["recipes_surveys"].assert_not_called()


def test_the_cli_message_names_the_project_json_keys_to_set(tmp_path, capsys):
    args = Namespace(command="survey", action="convert", project=_incomplete(tmp_path))
    with pytest.raises(SystemExit):
        _run(args, {"survey_convert": MagicMock()})
    out = capsys.readouterr().out
    for key in ("Basics.Name", "Basics.Authors", "Basics.Keywords", "StudyDesign.Timepoints"):
        assert key in out
