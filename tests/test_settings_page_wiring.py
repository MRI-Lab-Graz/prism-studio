"""Global settings live on their own /settings page, not on the project page."""

from __future__ import annotations

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


def test_settings_page_opens_without_a_project():
    # Settings (help, DataLad default, libraries) must be reachable before any project is picked.
    studio = _text(APP / "prism-studio.py")
    guard = studio[studio.index("def ensure_project_selected_first") :]

    assert 'path == "/settings"' in guard[: guard.index("\n\n\n")]


# --- the DataLad card for the loaded project lives on the Settings page ---------------------------

PROJECTS_JS = JS / "modules" / "projects"


def test_datalad_card_moved_from_the_project_page_to_the_settings_page():
    assert "datalad_section.html" not in _text(TEMPLATES / "includes" / "projects" / "page_sections.html")
    page = _text(TEMPLATES / "settings.html")
    assert "includes/projects/datalad_section.html" in page
    assert 'id="dataladSectionCard"' in _text(TEMPLATES / "includes" / "projects" / "datalad_section.html")


def test_datalad_card_logic_is_one_module_used_by_the_open_flow_and_the_settings_page():
    card = _text(PROJECTS_JS / "datalad-card.js")
    opener = _text(PROJECTS_JS / "open-project.js")
    index = _text(PROJECTS_JS / "index.js")

    assert "export function createDataladCard(" in card
    for name in ("function renderProjectBoxDataladState", "function runProjectBoxEnableDatalad", "function bindProjectBoxDataladActions"):
        assert name in card, name
        assert name not in opener, name
    assert "createDataladCard(" in opener
    assert "createDataladCard(" in index and "showDataladCard()" in index


def test_project_page_points_to_the_settings_page_for_datalad():
    opener = _text(PROJECTS_JS / "open-project.js")
    boot = _text(PROJECTS_JS / "page-bootstrap.js")

    assert 'href="/settings#dataladSection"' in opener
    assert "getElementById('dataladSection')" not in opener  # no in-page scroll handler any more
    assert "showDataladCard" not in boot
    assert "dataladSectionChevron" not in boot


def test_settings_page_still_runs_the_deep_datalad_status_for_tracked_projects():
    card = _text(PROJECTS_JS / "datalad-card.js")
    show = card[card.index("function showDataladCard()") :]

    assert "refreshDataladStatusDeep(" in show.split("\n    }\n")[0]


def test_datalad_card_exports_only_what_other_modules_use():
    card = _text(PROJECTS_JS / "datalad-card.js")
    exported = card[card.rindex("    return {") :]

    for name in ("formatElapsedDuration", "getSaveProgressElements", "normalizeDataladBoolean", "confirmEnableDatalad"):
        assert name not in exported, name
