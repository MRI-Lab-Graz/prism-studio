"""A test that saves app settings must not leak them into the next test (importing prism-studio.py saves
settings, which once made the survey parity tests resolve the official library from a stale `../official`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def test_a_saved_setting_exists_inside_its_own_test():
    from src.config import AppSettings, get_app_settings_path, save_app_settings

    save_app_settings(AppSettings(global_library_root="../official"), app_root=None)
    assert Path(get_app_settings_path(None)).exists()


def test_the_next_test_starts_without_settings():
    from src.config import get_app_settings_path

    assert not Path(get_app_settings_path(None)).exists()
