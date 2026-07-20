import os
import sys
import importlib
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

remote_browse_module = importlib.import_module(
    "src.web.blueprints.projects_remote_browse_blueprint"
)
projects_remote_browse_bp = remote_browse_module.projects_remote_browse_bp


def _build_app():
    app = Flask(__name__)
    app.register_blueprint(projects_remote_browse_bp)
    return app


def test_list_requires_host_or_a_parseable_ssh_target():
    app = _build_app()

    with app.test_client() as client:
        response = client.get("/api/projects/remote-browse/list")

    assert response.status_code == 400
    assert "SSH destination" in response.get_json()["error"]


def test_list_rejects_a_local_path_as_target():
    """A plain local path (no SSH host) isn't browsable by this endpoint --
    matches rsync_execution.is_remote_target's local-vs-SSH disambiguation."""
    app = _build_app()

    with app.test_client() as client:
        response = client.get(
            "/api/projects/remote-browse/list",
            query_string={"target": "/local/backup/path"},
        )

    assert response.status_code == 400


def test_list_parses_raw_target_into_host_and_path_on_first_call():
    app = _build_app()

    with patch(
        "src.web.blueprints.projects_remote_browse_blueprint.list_remote_directory",
        return_value={
            "success": True,
            "path": "/srv/backups/study1",
            "parent": "/srv/backups",
            "dirs": [{"name": "derivatives", "path": "/srv/backups/study1/derivatives"}],
        },
    ) as mock_list:
        with app.test_client() as client:
            response = client.get(
                "/api/projects/remote-browse/list",
                query_string={"target": "user@host:/srv/backups/study1"},
            )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["host"] == "user@host"
    assert payload["path"] == "/srv/backups/study1"
    assert payload["parent"] == "/srv/backups"
    assert payload["dirs"][0]["name"] == "derivatives"
    mock_list.assert_called_once_with("user@host", "/srv/backups/study1")


def test_list_uses_explicit_host_and_path_for_navigation_calls():
    """Once a host is known (returned by the first /list call), subsequent
    folder-navigation clicks pass host+path directly without re-parsing."""
    app = _build_app()

    with patch(
        "src.web.blueprints.projects_remote_browse_blueprint.list_remote_directory",
        return_value={"success": True, "path": "/srv/backups", "parent": "/srv", "dirs": []},
    ) as mock_list:
        with app.test_client() as client:
            response = client.get(
                "/api/projects/remote-browse/list",
                query_string={"host": "user@host", "path": "/srv/backups"},
            )

    assert response.status_code == 200
    mock_list.assert_called_once_with("user@host", "/srv/backups")


def test_list_reports_upstream_failure_as_502():
    app = _build_app()

    with patch(
        "src.web.blueprints.projects_remote_browse_blueprint.list_remote_directory",
        return_value={"success": False, "message": "Permission denied"},
    ):
        with app.test_client() as client:
            response = client.get(
                "/api/projects/remote-browse/list",
                query_string={"host": "user@host", "path": "/srv/backups"},
            )

    assert response.status_code == 502
    assert "Permission denied" in response.get_json()["error"]


def test_mkdir_requires_host():
    app = _build_app()

    with app.test_client() as client:
        response = client.post(
            "/api/projects/remote-browse/mkdir",
            json={"path": "/srv/backups/new-folder"},
        )

    assert response.status_code == 400


def test_mkdir_requires_path():
    app = _build_app()

    with app.test_client() as client:
        response = client.post(
            "/api/projects/remote-browse/mkdir",
            json={"host": "user@host"},
        )

    assert response.status_code == 400


def test_mkdir_creates_folder_and_returns_resolved_path():
    app = _build_app()

    with patch(
        "src.web.blueprints.projects_remote_browse_blueprint.create_remote_directory",
        return_value={"success": True, "path": "/srv/backups/study1/new-folder"},
    ) as mock_mkdir:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/remote-browse/mkdir",
                json={"host": "user@host", "path": "/srv/backups/study1/new-folder"},
            )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["path"] == "/srv/backups/study1/new-folder"
    mock_mkdir.assert_called_once_with("user@host", "/srv/backups/study1/new-folder")


def test_mkdir_reports_upstream_failure_as_502():
    app = _build_app()

    with patch(
        "src.web.blueprints.projects_remote_browse_blueprint.create_remote_directory",
        return_value={"success": False, "message": "mkdir: Permission denied"},
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/remote-browse/mkdir",
                json={"host": "user@host", "path": "/srv/backups/study1/new-folder"},
            )

    assert response.status_code == 502
    assert "Permission denied" in response.get_json()["error"]
