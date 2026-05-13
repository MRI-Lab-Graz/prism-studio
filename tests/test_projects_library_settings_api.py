from __future__ import annotations

import importlib
import sys
from pathlib import Path

from flask import Flask


def _build_app_for_blueprint():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    module = importlib.import_module("src.web.blueprints.projects_library_blueprint")
    app = Flask(__name__, root_path=str(app_root))
    app.register_blueprint(module.projects_library_bp)
    return app


def test_dedicated_terminal_setting_roundtrip(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()

    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    client = app.test_client()

    get_resp = client.get("/api/settings/dedicated-terminal")
    assert get_resp.status_code == 200
    get_data = get_resp.get_json()
    assert get_data["success"] is True
    assert get_data["show_dedicated_terminal"] is False

    post_resp = client.post(
        "/api/settings/dedicated-terminal",
        json={"show_dedicated_terminal": True},
    )
    assert post_resp.status_code == 200
    post_data = post_resp.get_json()
    assert post_data["success"] is True
    assert post_data["show_dedicated_terminal"] is True

    get_resp_again = client.get("/api/settings/dedicated-terminal")
    assert get_resp_again.status_code == 200
    get_data_again = get_resp_again.get_json()
    assert get_data_again["success"] is True
    assert get_data_again["show_dedicated_terminal"] is True


def test_backend_monitoring_verbose_setting_roundtrip(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()

    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    client = app.test_client()

    get_resp = client.get("/api/settings/backend-monitoring")
    assert get_resp.status_code == 200
    get_data = get_resp.get_json()
    assert get_data["success"] is True
    assert get_data["backend_monitoring"] is True
    assert get_data["backend_monitoring_verbose"] is False

    post_resp = client.post(
        "/api/settings/backend-monitoring",
        json={"backend_monitoring": True, "backend_monitoring_verbose": True},
    )
    assert post_resp.status_code == 200
    post_data = post_resp.get_json()
    assert post_data["success"] is True
    assert post_data["backend_monitoring"] is True
    assert post_data["backend_monitoring_verbose"] is True

    post_verbose_only_resp = client.post(
        "/api/settings/backend-monitoring",
        json={"backend_monitoring_verbose": False},
    )
    assert post_verbose_only_resp.status_code == 200
    post_verbose_only_data = post_verbose_only_resp.get_json()
    assert post_verbose_only_data["success"] is True
    assert post_verbose_only_data["backend_monitoring"] is True
    assert post_verbose_only_data["backend_monitoring_verbose"] is False


def test_get_modalities_returns_success(monkeypatch):
    app = _build_app_for_blueprint()
    module = importlib.import_module("src.web.blueprints.projects_library_blueprint")
    monkeypatch.setattr(module, "get_available_modalities", lambda: ["survey", "beh"])

    client = app.test_client()
    response = client.get("/api/projects/modalities")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["modalities"] == ["survey", "beh"]


def test_backend_monitoring_setting_requires_payload_keys(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    client = app.test_client()
    response = client.post("/api/settings/backend-monitoring", json={})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "backend_monitoring" in payload["error"]


def test_dedicated_terminal_setting_requires_payload_key(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    client = app.test_client()
    response = client.post("/api/settings/dedicated-terminal", json={})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "show_dedicated_terminal" in payload["error"]


def test_global_library_setting_rejects_missing_body():
    app = _build_app_for_blueprint()
    client = app.test_client()
    response = client.post("/api/settings/global-library", json={})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False


def test_global_library_setting_rejects_nonexistent_paths(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    client = app.test_client()
    response = client.post(
        "/api/settings/global-library",
        json={"global_template_library_path": str(tmp_path / "missing-library")},
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "Path does not exist" in payload["error"]


def test_global_library_setting_roundtrip_updates_connected_mode(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    library_dir = tmp_path / "official" / "library"
    recipe_dir = tmp_path / "official" / "recipe"
    library_dir.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)

    client = app.test_client()
    response = client.post(
        "/api/settings/global-library",
        json={
            "global_template_library_path": str(library_dir),
            "global_recipes_path": str(recipe_dir),
            "default_modalities": ["survey"],
            "connected_to_server": True,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["connected_to_server"] is True

    get_response = client.get("/api/settings/global-library")
    assert get_response.status_code == 200
    get_payload = get_response.get_json()
    assert get_payload["success"] is True
    assert get_payload["connected_to_server"] is True
    assert get_payload["global_template_library_path"] == str(library_dir)


def test_get_library_path_without_current_project(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    module = importlib.import_module("src.web.blueprints.projects_library_blueprint")
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)
    monkeypatch.setattr(module, "get_current_project", lambda: {"path": None, "name": None})

    client = app.test_client()
    response = client.get("/api/projects/library-path")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["project_library_path"] is None


def test_get_library_path_prefers_project_code_library(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    module = importlib.import_module("src.web.blueprints.projects_library_blueprint")
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    project_root = tmp_path / "projectA"
    code_library = project_root / "code" / "library"
    survey_dir = code_library / "survey"
    biometrics_dir = code_library / "biometrics"
    code_library.mkdir(parents=True)
    survey_dir.mkdir(parents=True)
    biometrics_dir.mkdir(parents=True)
    (project_root / "participants.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "get_current_project",
        lambda: {"path": str(project_root), "name": "projectA"},
    )

    client = app.test_client()
    response = client.get("/api/projects/library-path")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["project_library_exists"] is True
    assert payload["project_library_path"] == str(code_library)
    assert payload["structure"]["has_survey"] is True
    assert payload["structure"]["has_biometrics"] is True
    assert payload["structure"]["has_participants"] is True


def test_get_library_path_uses_external_path_when_project_library_missing(tmp_path, monkeypatch):
    app = _build_app_for_blueprint()
    module = importlib.import_module("src.web.blueprints.projects_library_blueprint")
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    project_root = tmp_path / "projectB"
    project_root.mkdir(parents=True)

    monkeypatch.setattr(
        module,
        "get_current_project",
        lambda: {"path": str(project_root), "name": "projectB"},
    )
    monkeypatch.setattr(
        importlib.import_module("src.config"),
        "get_effective_template_library_path",
        lambda *args, **kwargs: {
            "global_library_path": str(tmp_path / "official" / "library"),
            "project_library_path": None,
            "effective_external_path": str(tmp_path / "external" / "library"),
            "source": "project",
        },
    )

    client = app.test_client()
    response = client.get("/api/projects/library-path")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["project_library_exists"] is False
    assert payload["external_source"] == "project"
    assert payload["library_path"] == str(tmp_path / "external" / "library")
