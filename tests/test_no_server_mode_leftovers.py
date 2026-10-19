"""There is one picker; the converter modules carry no local/server-mode scaffolding."""

from pathlib import Path

CONVERTERS = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "modules" / "converter"
MODULES = ["survey-convert", "participants", "biometrics", "environment", "physio", "eyetracking"]
LEFTOVERS = ["prefersServerPicker", "PrismFileSystemMode", "prism-library-settings-changed", "PickerUiState"]


def test_converter_modules_have_no_server_mode_leftovers():
    found = {
        f"{name}.js: {token}"
        for name in MODULES
        for token in LEFTOVERS
        if token in (CONVERTERS / f"{name}.js").read_text(encoding="utf-8")
    }
    assert not found, sorted(found)
