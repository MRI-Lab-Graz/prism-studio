"""Every converter has ONE visible picker: a Browse button (the in-app browser).

No "Server" button, no visible native <input type=file>.
"""

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
CONVERTERS = ["survey", "participants", "biometrics", "environment", "physio", "eyetracking"]
# One entry per picker: id of its (hidden) native input and of its Browse button.
BROWSE_BUTTONS = {
    "survey": ["browseServerSurveyFileBtn"],
    "participants": ["participantsBrowseServerFileBtn"],
    "biometrics": ["browseServerBiometricsFileBtn"],
    "environment": ["browseServerEnvFileBtn"],
    "physio": ["browseServerPhysioFolderBtn"],
    "eyetracking": ["browseServerEyetrackingFolderBtn"],
}


def _read(name):
    return (TEMPLATES / f"converter_{name}.html").read_text(encoding="utf-8")


def _button(content, button_id):
    match = re.search(rf'<button[^>]*id="{button_id}"[^>]*>(.*?)</button>', content, re.S)
    assert match, f"{button_id} missing"
    return match.group(0), match.group(1)


def test_no_server_label_or_icon():
    for name in CONVERTERS:
        content = _read(name)
        assert "fa-server" not in content, name
        assert not re.search(r">\s*Server( Folder)?\s*<", content), name


def test_browse_button_is_always_visible_and_says_browse():
    for name, ids in BROWSE_BUTTONS.items():
        for button_id in ids:
            tag, label = _button(_read(name), button_id)
            assert "d-none" not in tag.split(">")[0], f"{name}: {button_id} is hidden"
            assert "Browse" in label, f"{name}: {button_id} label {label!r}"


# Optional side uploads (ID map, alias), not the source-file picker.
AUXILIARY_UPLOADS = ("convertIdMapFile",)


def test_native_file_inputs_are_not_visible():
    for name in CONVERTERS:
        for tag in re.findall(r'<input[^>]*type="file"[^>]*>', _read(name)):
            if any(f'id="{aux}"' in tag for aux in AUXILIARY_UPLOADS):
                continue
            assert "d-none" in tag or "visually-hidden" in tag, f"{name}: {tag}"


def test_participants_has_no_second_native_browse_button():
    assert "participantsChooseFileBtn" not in _read("participants")
