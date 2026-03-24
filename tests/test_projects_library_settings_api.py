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
