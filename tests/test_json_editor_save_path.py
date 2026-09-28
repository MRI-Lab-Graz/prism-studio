from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = PROJECT_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.json_editor_blueprint import create_json_editor_blueprint


def _build_app() -> Flask:
    app = Flask(
        __name__,
        root_path=str(APP_ROOT),
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = os.urandom(32)
    app.register_blueprint(create_json_editor_blueprint(bids_folder=None))
    return app


def test_save_path_writes_new_json_file(tmp_path):
    target = tmp_path / "custom_sidecar.json"

    app = _build_app()
    with app.test_client() as client:
        response = client.post(
            "/editor/api/save-path",
            json={"path": str(target), "data": {"Description": "hello"}},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert json.loads(target.read_text(encoding="utf-8")) == {"Description": "hello"}


def test_save_path_rejects_non_json_extension(tmp_path):
    target = tmp_path / "notes.txt"

    app = _build_app()
    with app.test_client() as client:
        response = client.post(
            "/editor/api/save-path", json={"path": str(target), "data": {}}
        )

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert not target.exists()


def test_save_path_rejects_missing_destination_folder(tmp_path):
    target = tmp_path / "missing-folder" / "file.json"

    app = _build_app()
    with app.test_client() as client:
        response = client.post(
            "/editor/api/save-path", json={"path": str(target), "data": {}}
        )

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_save_path_rejects_missing_path(tmp_path):
    app = _build_app()
    with app.test_client() as client:
        response = client.post("/editor/api/save-path", json={"data": {}})

    assert response.status_code == 400
    assert response.get_json()["success"] is False
