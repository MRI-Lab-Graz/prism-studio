"""Every converter has ONE visible picker: a Browse button (the in-app browser).

No "Server" button, no visible native <input type=file>.
"""

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
CONVERTERS = ["survey", "participants", "biometrics", "environment", "physio", "eyetracking"]
# One entry per picker: id of its (hidden) native input and of its Browse button.
BROWSE_BUTTONS = {
    "survey": ["browseSurveyFileBtn"],
    "participants": ["participantsBrowseFileBtn"],
    "biometrics": ["browseBiometricsFileBtn"],
    "environment": ["browseEnvFileBtn"],
    "physio": ["browsePhysioFolderBtn"],
    "eyetracking": ["browseEyetrackingFolderBtn"],
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


# ---- whole repo: no server button anywhere --------------------------------
ALL_TEMPLATES = sorted(TEMPLATES.rglob("*.html"))
# "Push to Server" publishes a project to a remote target; it is a feature, not a picker mode.
PUBLISH_FEATURE = "push_server_section.html"


def _picker_templates():
    return [p for p in ALL_TEMPLATES if p.name != PUBLISH_FEATURE]


def test_no_server_icon_or_label_in_any_template():
    offenders = []
    for path in _picker_templates():
        content = path.read_text(encoding="utf-8")
        if "fa-server" in content:
            offenders.append(f"{path.name}: fa-server")
        for label in re.findall(r"<button[^>]*>(.*?)</button>", content, re.S):
            text = re.sub(r"<[^>]+>", "", label)
            if re.search(r"\bServer\b", text):
                offenders.append(f"{path.name}: {' '.join(text.split())}")
    assert not offenders, offenders


def test_no_server_in_picker_element_ids():
    offenders = [
        f"{path.name}: {found}"
        for path in _picker_templates()
        for found in re.findall(r'id="([A-Za-z]*Server[A-Za-z]*)"', path.read_text(encoding="utf-8"))
    ]
    assert not offenders, offenders


def test_converter_browse_buttons_are_not_named_after_a_server():
    for name, ids in BROWSE_BUTTONS.items():
        for button_id in ids:
            assert "Server" not in button_id, button_id


FILES_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js"


def test_page_scripts_have_no_server_mode_leftovers():
    leftovers = ["prefersServerPicker", "PrismFileSystemMode", "prism-library-settings-changed", "applyRemotePickerUiState", "connectedToServer"]
    found = [
        f"{name}: {token}"
        for name in ("index.js", "file_management.js")
        for token in leftovers
        if token in (FILES_JS / name).read_text(encoding="utf-8")
    ]
    assert not found, found


def test_scripts_do_not_write_server_labels():
    offenders = [
        f"{path.relative_to(FILES_JS)}: {line.strip()[:80]}"
        for path in FILES_JS.rglob("*.js")
        if "vendor" not in path.parts and not path.name.endswith(".test.js")
        and path.name not in {"datalad_server.js", "rsync_server.js"}
        for line in path.read_text(encoding="utf-8").splitlines()
        if "fa-server" in line or re.search(r">\s*Server (File|Folder)\s*<|>Server (File|Folder)'", line)
    ]
    assert not offenders, offenders
