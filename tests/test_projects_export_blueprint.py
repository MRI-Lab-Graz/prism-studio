import os
import sys
import importlib
import threading
from pathlib import Path
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

projects_export_module = importlib.import_module(
    "src.web.blueprints.projects_export_blueprint"
)
projects_export_bp = projects_export_module.projects_export_bp


def _build_app():
    app = Flask(__name__)
    app.register_blueprint(projects_export_bp)
    return app


def test_projects_export_uses_fixed_internal_anonymization_settings(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    called = {}

    def fake_export_project(**kwargs):
        called.update(kwargs)
        output_zip = kwargs["output_zip"]
        Path(output_zip).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch(
        "src.web.export_project.export_project", side_effect=fake_export_project
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export",
                json={
                    "project_path": str(project_dir),
                    "anonymize": True,
                    "mask_questions": False,
                    "include_derivatives": True,
                    "include_code": False,
                    "include_analysis": False,
                },
            )

    assert response.status_code == 200
    assert called["anonymize"] is True
    assert called["mask_questions"] is False
    assert called["id_length"] == 8
    assert called["deterministic"] is False


def test_projects_export_sync_response_cleans_temp_zip_after_close(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    temp_zip = tmp_path / "response-export.zip"
    captured = {}

    def fake_mkstemp(suffix=".zip"):
        fd = os.open(temp_zip, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
        return fd, str(temp_zip)

    def fake_export_project(**kwargs):
        captured["output_zip"] = kwargs["output_zip"]
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch("src.web.blueprints.projects_export_blueprint.tempfile.mkstemp", side_effect=fake_mkstemp):
        with patch("src.web.export_project.export_project", side_effect=fake_export_project):
            with app.test_client() as client:
                response = client.post(
                    "/api/projects/export",
                    json={
                        "project_path": str(project_dir),
                        "anonymize": False,
                        "mask_questions": False,
                    },
                )

    assert response.status_code == 200
    assert Path(captured["output_zip"]) == temp_zip
    assert temp_zip.exists()

    _ = response.get_data()

    assert not temp_zip.exists()


def test_export_download_keeps_saved_zip_and_cleans_job_after_close(tmp_path):
    app = _build_app()

    zip_path = tmp_path / "saved-export.zip"
    zip_path.write_bytes(b"PK\x03\x04")
    job_id = "job-download"

    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
        projects_export_module._export_jobs[job_id] = {
            "status": "complete",
            "percent": 100,
            "message": "Export complete",
            "zip_path": str(zip_path),
            "filename": "saved-export.zip",
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": 0.0,
            "updated_at": 0.0,
            "done_at": 1.0,
        }

    with app.test_client() as client:
        response = client.get(f"/api/projects/export/{job_id}/download")

    assert response.status_code == 200
    assert zip_path.exists()

    _ = response.get_data()

    assert zip_path.exists()
    with projects_export_module._export_lock:
        assert job_id not in projects_export_module._export_jobs


def test_export_job_store_prunes_done_jobs_after_ttl(monkeypatch):
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
        projects_export_module._last_export_prune_at = 0.0
        projects_export_module._export_jobs["expired"] = {
            "status": "complete",
            "percent": 100,
            "message": "old",
            "zip_path": "/tmp/old.zip",
            "filename": "old.zip",
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": 0.0,
            "updated_at": 0.0,
            "done_at": 10.0,
        }
        projects_export_module._export_jobs["active"] = {
            "status": "running",
            "percent": 25,
            "message": "running",
            "zip_path": None,
            "filename": None,
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": 100.0,
            "updated_at": 100.0,
            "done_at": None,
        }

    monkeypatch.setattr(projects_export_module, "_EXPORT_JOB_TTL_SECONDS", 50.0)
    monkeypatch.setattr(projects_export_module, "_EXPORT_JOB_PRUNE_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(projects_export_module, "_export_now", lambda: 100.0)

    active_job = projects_export_module._get_export_job("active")

    assert active_job["status"] == "running"
    with projects_export_module._export_lock:
        assert "expired" not in projects_export_module._export_jobs
        assert "active" in projects_export_module._export_jobs
