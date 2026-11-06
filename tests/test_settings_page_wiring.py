"""Global settings live on their own /settings page, not on the project page."""

from __future__ import annotations

import re
import importlib
import sys
from pathlib import Path

from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "app"
TEMPLATES = APP / "templates"
JS = APP / "static" / "js"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_project_page_no_longer_carries_the_settings_card():
    assert "settings_section.html" not in _text(TEMPLATES / "includes" / "projects" / "page_sections.html")


def test_settings_page_has_the_settings_card_beginner_mode_and_datalad_preset():
    page = _text(TEMPLATES / "settings.html")

    assert 'id="settingsRoot"' in page
    assert "includes/projects/settings_section.html" in page
    assert 'id="beginnerHelpModeToggle"' in page
    assert 'id="dataladForNewProjectsToggle"' in page


def test_navbar_links_to_settings_and_beginner_mode_left_the_projects_menu():
    base = _text(TEMPLATES / "base.html")

    assert "url_for('projects_library.settings_page')" in base
    assert 'id="beginnerHelpModeToggle"' not in base


def test_main_initializes_the_settings_page():
    main = _text(JS / "main.js")

    assert "getElementById('settingsRoot')" in main
    assert "initializeSettingsPage" in main


def test_project_page_bootstrap_no_longer_owns_the_settings_card_but_keeps_the_import_button_in_sync():
    boot = _text(JS / "modules" / "projects" / "page-bootstrap.js")

    for name in ("initBackendMonitoringToggle", "initDedicatedTerminalToggle", "loadGlobalSettings", "useDefaultLibrary"):
        assert name not in boot, name
    assert "loadStudyApplicationImportVisibility" in boot
    assert "applyDataladDefaultToCreateForm" in boot


def _client(tmp_path, monkeypatch):
    sys.path.insert(0, str(APP)) if str(APP) not in sys.path else None
    module = importlib.import_module("src.web.blueprints.projects_library_blueprint")
    from src import config

    monkeypatch.setattr(config, "_get_user_app_settings_dir", lambda: tmp_path)
    app = Flask(__name__, root_path=str(APP))
    app.register_blueprint(module.projects_library_bp)
    return app.test_client()


def test_datalad_preset_roundtrips_through_the_settings_routes(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    assert client.get("/api/settings/global-library").get_json()["datalad_for_new_projects"] is False
    posted = client.post("/api/settings/global-library", json={"datalad_for_new_projects": True}).get_json()
    assert posted["success"] is True
    assert client.get("/api/settings/global-library").get_json()["datalad_for_new_projects"] is True


def test_wcag_enhanced_view_roundtrips_through_the_settings_routes(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    assert client.get("/api/settings/global-library").get_json()["wcag_enhanced_view"] is False
    posted = client.post("/api/settings/global-library", json={"wcag_enhanced_view": True}).get_json()
    assert posted["success"] is True and posted["wcag_enhanced_view"] is True
    assert client.get("/api/settings/global-library").get_json()["wcag_enhanced_view"] is True


def test_wcag_enhanced_view_toggle_page_attribute_and_css_are_wired():
    assert 'id="wcagEnhancedViewToggle"' in _text(TEMPLATES / "settings.html")
    assert "data-wcag" in _text(TEMPLATES / "base.html")
    css = _text(APP / "static" / "css" / "studio-theme.css")
    assert "html[data-wcag] .studio-theme :focus-visible" in css
    # every rule of the accessibility section sits behind the switch: the default view is the original look
    section = css[css.index("/* Accessibility (WCAG AA") :]
    bare = re.findall(r"^\s*((?:\.studio-theme|html)[^;{}]*?)\s*[,{]\s*$", section, re.M)
    assert [rule for rule in bare if "html[data-wcag]" not in rule] == []
    assert "html[data-wcag] html" not in css  # a rule for <html> itself is html[data-wcag] {, not a descendant


def test_settings_page_opens_without_a_project():
    # Settings (help, DataLad default, libraries) must be reachable before any project is picked.
    studio = _text(APP / "prism-studio.py")
    guard = studio[studio.index("def ensure_project_selected_first") :]

    assert 'path == "/settings"' in guard[: guard.index("\n\n\n")]


# --- DataLad for the loaded project lives on its own page (/projects/datalad) --------------------

PROJECTS_JS = JS / "modules" / "projects"


def test_settings_page_keeps_name_and_email_but_not_the_datalad_card():
    page = _text(TEMPLATES / "settings.html")
    index = _text(PROJECTS_JS / "index.js")
    settings_init = index[index.index("export function initializeSettingsPage()") :].split("\n}\n")[0]

    assert "datalad_section.html" not in page
    assert 'id="gitIdentityForm"' in page
    assert "url_for('projects.datalad_page')" in page  # where the project's own DataLad tracking went
    assert "initGitIdentityForm();" in settings_init
    assert "createDataladCard" not in settings_init and "showDataladCard" not in settings_init


def test_project_page_no_longer_shows_datalad():
    opener = _text(PROJECTS_JS / "open-project.js")
    boot = _text(PROJECTS_JS / "page-bootstrap.js")

    assert "/settings#dataladSection" not in opener  # the loaded-project box has no DataLad row any more
    assert "getElementById('dataladSection')" not in opener  # no in-page scroll handler any more
    assert "showDataladCard" not in boot
    assert "dataladSectionChevron" not in boot


def test_no_page_hardcodes_the_wcag_green():
    # The darker green belongs to the WCAG enhanced view only; pages take the theme colour so the switch changes them.
    hits = [
        str(path.relative_to(APP))
        for pattern in ("static/css/**/*.css", "static/js/*.js", "templates/**/*.html")
        for path in APP.glob(pattern)
        if path.name != "studio-theme.css" and "#1a744d" in _text(path)
    ]
    assert sorted(set(hits) - {"static/css/projects/cards.css"}) == []  # cards.css only has it as a var() fallback
