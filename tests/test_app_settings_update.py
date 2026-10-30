"""The Settings page is commands too: `settings show|set` and the page's routes run one function."""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src import config  # noqa: E402
from src.settings_update import SETTINGS, SettingsError, settings_as_dict, update_app_settings  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_get_user_app_settings_dir", lambda: tmp_path / "settings")


def test_valid_changes_are_applied_and_saved(tmp_path):
    mine = tmp_path / "mine"
    mine.mkdir()
    settings = update_app_settings(APP, {"personal_library_path": str(mine), "backend_monitoring": False, "default_modalities": ["survey"]})

    assert settings.personal_library_path == str(mine) and settings.backend_monitoring is False
    saved = config.load_app_settings(app_root=str(APP))
    assert saved.personal_library_path == str(mine) and saved.default_modalities == ["survey"]


def test_an_empty_path_clears_the_setting(tmp_path):
    mine = tmp_path / "mine"
    mine.mkdir()
    update_app_settings(APP, {"personal_library_path": str(mine)})
    assert update_app_settings(APP, {"personal_library_path": ""}).personal_library_path is None


@pytest.mark.parametrize("changes, message", [
    ({"personal_library_path": "/no/such/folder"}, "does not exist"),
    ({"global_template_library_path": "/no/such/folder"}, "does not exist"),
    ({"export_defacing_confirmation_mode": "sometimes"}, "risk"),
    ({"no_such_setting": 1}, "Unknown setting"),
])
def test_invalid_changes_are_rejected_and_nothing_is_saved(changes, message):
    before = settings_as_dict(config.load_app_settings(app_root=str(APP)))
    with pytest.raises(SettingsError, match=message):
        update_app_settings(APP, changes)
    assert settings_as_dict(config.load_app_settings(app_root=str(APP))) == before


def test_one_bad_value_stops_the_whole_change(tmp_path):
    mine = tmp_path / "mine"
    mine.mkdir()
    with pytest.raises(SettingsError):
        update_app_settings(APP, {"personal_library_path": str(mine), "export_defacing_confirmation_mode": "nope"})
    assert config.load_app_settings(app_root=str(APP)).personal_library_path is None


def _set_args(**values):
    from src.cli.commands.settings import cmd_settings_set  # noqa: F401

    flags = {name: None for name in SETTINGS}
    flags.update(values)
    return SimpleNamespace(**flags)


def test_the_command_sets_and_shows_the_same_settings(tmp_path, capsys):
    from src.cli.commands.settings import cmd_settings_set, cmd_settings_show

    mine = tmp_path / "mine"
    mine.mkdir()
    cmd_settings_set(_set_args(personal_library_path=str(mine), show_dedicated_terminal="on", default_modalities="survey,biometrics"))
    capsys.readouterr()
    cmd_settings_show(SimpleNamespace(json=True))

    shown = json.loads(capsys.readouterr().out)
    assert shown["personal_library_path"] == str(mine)
    assert shown["show_dedicated_terminal"] is True
    assert shown["default_modalities"] == ["survey", "biometrics"]


def test_the_command_refuses_a_bad_value_with_the_reason(tmp_path, capsys):
    from src.cli.commands.settings import cmd_settings_set

    with pytest.raises(SystemExit):
        cmd_settings_set(_set_args(personal_library_path="/no/such/folder"))
    assert "does not exist" in capsys.readouterr().out


def test_every_setting_has_a_command_flag():
    from src.cli.parser import build_prism_tools_parsers

    _root, parsers = build_prism_tools_parsers(APP)
    sub = [a for a in parsers["settings"]._actions if isinstance(a, argparse._SubParsersAction)][0]
    flags = {a.dest for a in sub.choices["set"]._actions}
    assert set(SETTINGS) <= flags, sorted(set(SETTINGS) - flags)
