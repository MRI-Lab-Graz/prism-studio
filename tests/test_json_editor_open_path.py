from __future__ import annotations

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


def test_open_path_reads_arbitrary_json_file(tmp_path):
    json_file = tmp_path / "task-rest_events.json"
    json_file.write_text('{"onset": {"Description": "onset time"}}', encoding="utf-8")

    app = _build_app()
    with app.test_client() as client:
        response = client.get("/editor/api/open-path", query_string={"path": str(json_file)})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "success": True,
        "data": {"onset": {"Description": "onset time"}},
        "filename": "task-rest_events.json",
    }


def test_open_path_rejects_missing_file(tmp_path):
    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/editor/api/open-path",
            query_string={"path": str(tmp_path / "missing.json")},
        )

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_open_path_rejects_non_json_extension(tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("hello", encoding="utf-8")

    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/editor/api/open-path", query_string={"path": str(text_file)}
        )

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_open_path_rejects_invalid_json(tmp_path):
    bad_json = tmp_path / "broken.json"
    bad_json.write_text("{not valid json", encoding="utf-8")

    app = _build_app()
    with app.test_client() as client:
        response = client.get(
            "/editor/api/open-path", query_string={"path": str(bad_json)}
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "Invalid JSON" in payload["error"]
