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
