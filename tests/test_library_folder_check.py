from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.config import library_folder_error, recipes_folder_error  # noqa: E402


def test_library_folder_error(tmp_path):
    assert "survey/" in library_folder_error(str(tmp_path))
    (tmp_path / "survey").mkdir()
    assert library_folder_error(str(tmp_path)) is None


def test_cli_check_path_reports_missing_survey(tmp_path, capsys):
    from src.cli.commands.library import cmd_library_check_path

    args = type("A", (), {"path": str(tmp_path), "recipes": False})()
    try:
        cmd_library_check_path(args)
    except SystemExit as e:
        assert e.code == 1
    else:
        raise AssertionError("expected SystemExit(1)")
    assert "survey/" in capsys.readouterr().err


def test_recipes_folder_error(tmp_path):
    assert "survey/" in recipes_folder_error(str(tmp_path))
    (tmp_path / "survey").mkdir()
    assert recipes_folder_error(str(tmp_path)) is None


def test_cli_check_path_recipes_flag(tmp_path, capsys):
    from src.cli.commands.library import cmd_library_check_path

    (tmp_path / "survey").mkdir()
    cmd_library_check_path(type("A", (), {"path": str(tmp_path), "recipes": True})())
    assert "valid" in capsys.readouterr().out
