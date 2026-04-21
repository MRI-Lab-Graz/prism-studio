import os
import sys
import importlib
import threading
import time
from pathlib import Path
from types import SimpleNamespace
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

    with patch(
        "src.web.blueprints.projects_export_blueprint.tempfile.mkstemp",
        side_effect=fake_mkstemp,
    ):
        with patch(
            "src.web.export_project.export_project", side_effect=fake_export_project
        ):
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
        now = time.monotonic()
        projects_export_module._export_jobs[job_id] = {
            "status": "complete",
            "percent": 100,
            "message": "Export complete",
            "zip_path": str(zip_path),
            "filename": "saved-export.zip",
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": now,
            "updated_at": now,
            "done_at": now,
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
    monkeypatch.setattr(
        projects_export_module, "_EXPORT_JOB_PRUNE_INTERVAL_SECONDS", 0.0
    )
    monkeypatch.setattr(projects_export_module, "_export_now", lambda: 100.0)

    active_job = projects_export_module._get_export_job("active")

    assert active_job["status"] == "running"
    with projects_export_module._export_lock:
        assert "expired" not in projects_export_module._export_jobs
        assert "active" in projects_export_module._export_jobs


def test_export_job_blocks_when_pre_export_validation_has_errors(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-errors"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "both",
    }

    with patch(
        "src.web.validation.run_validation",
        return_value=(
            [("ERROR", "Broken dataset", str(project_dir))],
            SimpleNamespace(total_files=1),
        ),
    ):
        with patch("src.web.export_project.export_project") as mock_do_export:
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "error"
    assert "Export blocked" in (job.get("error") or "")
    mock_do_export.assert_not_called()


def test_export_job_allows_warnings_only_pre_export_validation(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-warnings"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    def fake_export_project(**kwargs):
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 1, "files_anonymized": 0, "participant_count": 0}

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "prism",
    }

    with patch(
        "src.web.validation.run_validation",
        return_value=(
            [("WARNING", "Missing optional metadata", str(project_dir))],
            SimpleNamespace(total_files=1),
        ),
    ):
        with patch(
            "src.web.export_project.export_project",
            side_effect=fake_export_project,
        ):
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "complete"
    assert Path(job["zip_path"]).exists()


def test_export_job_skips_validation_when_mode_is_ignore(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-ignore"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    def fake_export_project(**kwargs):
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 1, "files_anonymized": 0, "participant_count": 0}

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "ignore",
    }

    with patch("src.web.validation.run_validation") as mock_run_validation:
        with patch(
            "src.web.export_project.export_project",
            side_effect=fake_export_project,
        ):
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "complete"
    mock_run_validation.assert_not_called()


def test_export_job_does_not_block_on_non_error_issue_levels(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-info-only"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    def fake_export_project(**kwargs):
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 1, "files_anonymized": 0, "participant_count": 0}

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "both",
    }

    with patch(
        "src.web.validation.run_validation",
        return_value=(
            [("INFO", "Dataset summary information", str(project_dir))],
            SimpleNamespace(total_files=1),
        ),
    ):
        with patch(
            "src.web.export_project.export_project",
            side_effect=fake_export_project,
        ):
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "complete"
