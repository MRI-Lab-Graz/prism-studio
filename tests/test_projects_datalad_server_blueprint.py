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

datalad_server_module = importlib.import_module(
    "src.web.blueprints.projects_datalad_server_blueprint"
)
projects_datalad_server_bp = datalad_server_module.projects_datalad_server_bp


def _build_app():
    app = Flask(__name__)
    app.register_blueprint(projects_datalad_server_bp)
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

    def run_now(self):
        self.target(*self.args)


def _project_dir(tmp_path) -> Path:
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    return project_dir


# ===== A5: async job lifecycle for "Push to DataLad Server" =====
# (start -> status, cancel -> status, config persistence)


def test_datalad_server_status_route_uses_project_manager(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.project_manager.ProjectManager.get_ria_status",
        return_value={"connected": True, "sibling_name": "ria-store"},
    ) as mock_status:
        with app.test_client() as client:
            response = client.get(
                "/api/projects/datalad-server/status",
                query_string={"project_path": str(project_dir)},
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("connected") is True
    mock_status.assert_called_once_with(project_dir)


def test_datalad_server_save_config_persists_to_prismrc(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with app.test_client() as client:
        response = client.post(
            "/api/projects/datalad-server/config",
            json={
                "project_path": str(project_dir),
                "ria_url": "ria+ssh://user@host/store",
                "sibling_name": "my-sibling",
                "alias": "my-study",
            },
        )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("ria_url") == "ria+ssh://user@host/store"
    assert payload.get("sibling_name") == "my-sibling"

    saved = json.loads(Path(payload["config_path"]).read_text(encoding="utf-8"))
    assert saved.get("riaStoreUrl") == "ria+ssh://user@host/store"
    assert saved.get("siblingName") == "my-sibling"
    assert saved.get("siblingAlias") == "my-study"


def test_datalad_server_sync_job_reaches_complete_status_on_success(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_datalad_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_ria",
        return_value={"success": True, "message": "Synced to RIA store."},
    ):
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/datalad-server/sync/start",
                json={"project_path": str(project_dir), "ria_url": "ria+ssh://user@host/store"},
            )
            assert start_response.status_code == 200
            job_id = start_response.get_json()["job_id"]

            # The thread never actually started (only captured); run its
            # target synchronously now to simulate the background job.
            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/datalad-server/sync/{job_id}/status"
            )

    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["status"] == "complete"
    assert status_payload["result"]["success"] is True


def test_datalad_server_sync_job_reaches_error_status_on_failure(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_datalad_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_ria",
        return_value={"success": False, "message": "Could not connect to RIA store."},
    ):
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/datalad-server/sync/start",
                json={"project_path": str(project_dir), "ria_url": "ria+ssh://user@host/store"},
            )
            job_id = start_response.get_json()["job_id"]

            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/datalad-server/sync/{job_id}/status"
            )

    status_payload = status_response.get_json()
    assert status_payload["status"] == "error"
    assert "Could not connect" in status_payload["error"]


def test_datalad_server_sync_cancel_sets_cancel_event_before_job_runs(tmp_path):
    """Cancelling before the (fake) background thread runs must make the job
    land in 'cancelled', proving the cancel_event actually reaches is_cancelled()."""
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_datalad_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.sync_project_to_ria"
    ) as mock_sync:
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        def _fake_sync(project_path, *, progress_callback=None, is_cancelled=None, **kwargs):
            # Simulate the manager honoring cancellation mid-flight.
            return {"success": False, "message": "Cancelled before push."}

        mock_sync.side_effect = _fake_sync

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/datalad-server/sync/start",
                json={"project_path": str(project_dir), "ria_url": "ria+ssh://user@host/store"},
            )
            job_id = start_response.get_json()["job_id"]

            cancel_response = client.delete(
                f"/api/projects/datalad-server/sync/{job_id}/cancel"
            )
            assert cancel_response.status_code == 200
            assert cancel_response.get_json()["cancelled"] is True

            # Now run the (fake) background thread's target -- is_cancelled()
            # should report True since the cancel event was set above.
            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/datalad-server/sync/{job_id}/status"
            )

    assert status_response.get_json()["status"] == "cancelled"


def test_datalad_server_finalize_start_forwards_verify_mode_and_mark_annex_dead(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_datalad_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.finalize_project_upload",
        return_value={"success": True, "message": "Push verified and local sibling disconnected."},
    ) as mock_finalize:
        captured = {}

        def _capture(target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            return _FakeThread(target=target, args=args, daemon=daemon)

        mock_thread_cls.side_effect = _capture

        with app.test_client() as client:
            start_response = client.post(
                "/api/projects/datalad-server/finalize/start",
                json={
                    "project_path": str(project_dir),
                    "ria_url": "ria+ssh://user@host/store",
                    "verify_mode": "full",
                    "mark_annex_dead": True,
                },
            )
            job_id = start_response.get_json()["job_id"]

            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/datalad-server/finalize/{job_id}/status"
            )

    mock_finalize.assert_called_once()
    _, call_kwargs = mock_finalize.call_args
    assert call_kwargs["verify_mode"] == "full"
    assert call_kwargs["mark_annex_dead"] is True
    assert status_response.get_json()["status"] == "complete"


def test_datalad_server_finalize_job_reaches_error_status_when_push_unverified(tmp_path):
    app = _build_app()
    project_dir = _project_dir(tmp_path)

    with patch(
        "src.web.blueprints.projects_datalad_server_blueprint.threading.Thread"
    ) as mock_thread_cls, patch(
        "src.project_manager.ProjectManager.finalize_project_upload",
        return_value={
            "success": False,
            "verified": False,
            "message": "Push could not be verified: 1 unresolved file(s). Sibling left registered for retry.",
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
                "/api/projects/datalad-server/finalize/start",
                json={"project_path": str(project_dir), "ria_url": "ria+ssh://user@host/store"},
            )
            job_id = start_response.get_json()["job_id"]

            captured["target"](*captured["args"])

            status_response = client.get(
                f"/api/projects/datalad-server/finalize/{job_id}/status"
            )

    status_payload = status_response.get_json()
    assert status_payload["status"] == "error"
    assert "unresolved" in status_payload["error"]


def test_datalad_server_sync_status_route_reports_job_not_found(tmp_path):
    app = _build_app()

    with app.test_client() as client:
        response = client.get(
            "/api/projects/datalad-server/sync/does-not-exist/status"
        )

    assert response.status_code == 404
