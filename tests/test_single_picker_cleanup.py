"""The 'connected to server' mode is gone: the in-app picker is the only picker."""

import re
from pathlib import Path

from src.config import AppSettings

JS_ROOT = Path(__file__).resolve().parents[1] / "app" / "static" / "js"


def test_no_script_disables_a_native_input_because_of_server_mode():
    # prefersServerPicker() is always true now, so this would disable the input forever.
    offenders = [
        str(p.relative_to(JS_ROOT))
        for p in JS_ROOT.rglob("*.js")
        if re.search(r"\.disabled\s*=\s*connectedToServer", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_settings_have_no_connected_to_server_flag():
    assert not hasattr(AppSettings(), "connected_to_server")


def test_project_file_browser_has_no_dead_native_picker_fallback():
    text = (JS_ROOT / "modules" / "projects" / "file-browser.js").read_text(encoding="utf-8")
    assert "isPickerValidationError" not in text
    assert "fallback:" not in text
