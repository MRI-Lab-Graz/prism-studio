import json
import os
import sys
import importlib
from pathlib import Path
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

rsync_server_module = importlib.import_module(
    "src.web.blueprints.projects_rsync_server_blueprint"
)
projects_rsync_server_bp = rsync_server_module.projects_rsync_server_bp


def _build_app():
    app = Flask(__name__)
    app.register_blueprint(projects_rsync_server_bp)
    return app


class _FakeThread:
    """Captures the background job's target/args instead of running it, so a
    test can invoke the job synchronously (to assert completion) or send a
    cancel request before invoking it (to assert cancellation is honored)."""

    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args

    def start(self):
        pass


def _project_dir(tmp_path) -> Path:
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    return project_dir


# ===== A5: async job lifecycle for "Push to Remote Server" (rsync) =====


def test_rsync_server_status_route_uses_project_manager(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.project_manager.ProjectManager.get_rsync_status",
        return_value={"configured": True, "rsync_available": True},
    ) as mock_status:
        with app.test_client() as client:
            response = client.get(
                "/api/projects/rsync-server/status",
                query_string={"project_path": str(project_dir)},
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("configured") is True
    mock_status.assert_called_once_with(project_dir)


def test_rsync_server_save_config_persists_to_prismrc(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with app.test_client() as client:
        response = client.post(
            "/api/projects/rsync-server/config",
            json={
                "project_path": str(project_dir),
                "remote_target": "researcher@host:/srv/backups/study1",
                "remote_label": "Lab NAS",
            },
        )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("remote_target") == "researcher@host:/srv/backups/study1"
    assert payload.get("remote_label") == "Lab NAS"

    saved = json.loads(Path(payload["config_path"]).read_text(encoding="utf-8"))
    assert saved.get("rsyncRemoteTarget") == "researcher@host:/srv/backups/study1"
    assert saved.get("rsyncRemoteLabel") == "Lab NAS"


def test_rsync_server_sync_job_reaches_complete_status_on_success(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_rsync_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_remote",
        return_value={"success": True, "message": "Copied to remote destination."},
    ):
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/rsync-server/sync/start",
                json={
                    "project_path": str(project_dir),
                    "remote_target": "researcher@host:/srv/backups/study1",
                },
            )
            assert start_response.status_code == 200
            job_id = start_response.get_json()["job_id"]

            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/rsync-server/sync/{job_id}/status"
            )

    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["status"] == "complete"
    assert status_payload["result"]["success"] is True


def test_rsync_server_sync_job_reaches_error_status_when_verification_finds_mismatches(
    tmp_path,
):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_rsync_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_remote",
        return_value={
            "success": False,
            "message": "Copy ran, but verification found differences: 1 file(s) differ.",
        },
    ):
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/rsync-server/sync/start",
                json={
                    "project_path": str(project_dir),
                    "remote_target": "researcher@host:/srv/backups/study1",
                    "verify": True,
                },
            )
            job_id = start_response.get_json()["job_id"]

            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/rsync-server/sync/{job_id}/status"
            )

    status_payload = status_response.get_json()
    assert status_payload["status"] == "error"
    assert "differ" in status_payload["error"]


def test_rsync_server_save_config_persists_exclude_patterns(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with app.test_client() as client:
        response = client.post(
            "/api/projects/rsync-server/config",
            json={
                "project_path": str(project_dir),
                "remote_target": "researcher@host:/srv/backups/study1",
                "exclude_patterns": ["derivatives/", " ", "*.tmp", "derivatives/"],
            },
        )

    assert response.status_code == 200
    payload = response.get_json() or {}
    # blanks dropped, duplicates collapsed, order preserved
    assert payload.get("exclude_patterns") == ["derivatives/", "*.tmp"]

    saved = json.loads(Path(payload["config_path"]).read_text(encoding="utf-8"))
    assert saved.get("rsyncExcludePatterns") == ["derivatives/", "*.tmp"]


def test_rsync_server_sync_forwards_exclude_patterns(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_rsync_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_remote",
        return_value={"success": True, "message": "ok"},
    ) as mock_sync:
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/rsync-server/sync/start",
                json={
                    "project_path": str(project_dir),
                    "remote_target": "researcher@host:/srv/backups/study1",
                    "exclude_patterns": ["derivatives/", "", "*.tmp"],
                },
            )
            job_id = start_response.get_json()["job_id"]
            captured["target"](*captured["args"])

    mock_sync.assert_called_once()
    _, call_kwargs = mock_sync.call_args
    assert call_kwargs["exclude_patterns"] == ["derivatives/", "*.tmp"]


def test_rsync_server_sync_omits_exclude_patterns_when_not_provided(tmp_path):
    """No exclude_patterns in the request falls back to the project's saved patterns."""
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_rsync_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_remote",
        return_value={"success": True, "message": "ok"},
    ) as mock_sync:
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/rsync-server/sync/start",
                json={
                    "project_path": str(project_dir),
                    "remote_target": "researcher@host:/srv/backups/study1",
                },
            )
            job_id = start_response.get_json()["job_id"]
            captured["target"](*captured["args"])

    mock_sync.assert_called_once()
    _, call_kwargs = mock_sync.call_args
    assert call_kwargs["exclude_patterns"] is None


def test_rsync_server_sync_forwards_verify_flag(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_rsync_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_remote",
        return_value={"success": True, "message": "ok"},
    ) as mock_sync:
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/rsync-server/sync/start",
                json={
                    "project_path": str(project_dir),
                    "remote_target": "researcher@host:/srv/backups/study1",
                    "verify": True,
                },
            )
            job_id = start_response.get_json()["job_id"]
            captured["target"](*captured["args"])

    mock_sync.assert_called_once()
    _, call_kwargs = mock_sync.call_args
    assert call_kwargs["verify"] is True


def test_rsync_server_sync_cancel_sets_cancel_event_before_job_runs(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_rsync_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_remote"
    ) as mock_sync:
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        def _fake_sync(project_path, *, progress_callback=None, is_cancelled=None, **kwargs):
            return {"success": False, "message": "Cancelled."}

        mock_sync.side_effect = _fake_sync

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/rsync-server/sync/start",
                json={
                    "project_path": str(project_dir),
                    "remote_target": "researcher@host:/srv/backups/study1",
                },
            )
            job_id = start_response.get_json()["job_id"]

            cancel_response = client.delete(
                f"/api/projects/rsync-server/sync/{job_id}/cancel"
            )
            assert cancel_response.status_code == 200
            assert cancel_response.get_json()["cancelled"] is True

            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/rsync-server/sync/{job_id}/status"
            )

    assert status_response.get_json()["status"] == "cancelled"


def test_rsync_server_sync_status_route_reports_job_not_found():
    app = _build_app()

    with app.test_client() as client:
        response = client.get(
            "/api/projects/rsync-server/sync/does-not-exist/status"
        )

    assert response.status_code == 404
