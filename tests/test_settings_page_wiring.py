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
