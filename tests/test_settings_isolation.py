"""A test that saves app settings must not leak them into the next test (importing prism-studio.py saves
settings, which once made the survey parity tests resolve the official library from a stale `../official`)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def test_a_saved_setting_exists_inside_its_own_test():
    from src.config import AppSettings, get_app_settings_path, save_app_settings

    save_app_settings(AppSettings(global_library_root="../official"), app_root=None)
    assert Path(get_app_settings_path(None)).exists()


def test_the_next_test_starts_with_default_settings():
    from src.config import get_app_settings_path, load_app_settings

    assert load_app_settings(None).global_library_root is None
    assert json.loads(Path(get_app_settings_path(None)).read_text(encoding="utf-8")) == {}
