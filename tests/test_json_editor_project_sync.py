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


def test_json_editor_loads_project_file_when_session_points_to_project_json(tmp_path):
    project_root = tmp_path / "demo-project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.json").write_text("{}", encoding="utf-8")
    (project_root / "dataset_description.json").write_text(
        '{"Name": "Demo dataset"}',
        encoding="utf-8",
    )

    app = _build_app()

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["current_project_path"] = str(project_root / "project.json")

        response = client.get("/editor/api/file/dataset_description")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {"success": True, "data": {"Name": "Demo dataset"}}


def test_json_editor_does_not_keep_previous_project_after_session_path_becomes_stale(
    tmp_path,
):
    project_root = tmp_path / "demo-project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "dataset_description.json").write_text(
        '{"Name": "Demo dataset"}',
        encoding="utf-8",
    )

    app = _build_app()

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["current_project_path"] = str(project_root)

        first_response = client.get("/editor/api/file/dataset_description")

        with client.session_transaction() as session:
            session["current_project_path"] = str(
                tmp_path / "missing-project" / "project.json"
            )

        second_response = client.get("/editor/api/file/dataset_description")

    assert first_response.status_code == 200
    first_payload = first_response.get_json()
    assert first_payload == {"success": True, "data": {"Name": "Demo dataset"}}

    assert second_response.status_code == 400
    second_payload = second_response.get_json()
    assert second_payload["success"] is False
    assert "No BIDS folder set" in second_payload["error"]
