import io
import os
import sys
from pathlib import Path

from flask import Flask


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints import validation as validation_blueprint_module
from src.web.blueprints.validation import validation_bp
from src.web.validation import clear_progress, complete_progress, get_progress, update_progress


def _build_app() -> Flask:
    app = Flask(
        __name__,
        root_path=str(APP_ROOT),
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = "test-secret"
    app.register_blueprint(validation_bp)
    return app


def test_progress_helpers_keep_completion_metadata():
    job_id = "job-progress-test"
    clear_progress(job_id)

    update_progress(
        job_id,
        15,
        "Scanning dataset...",
        phase="validation",
        progress_mode="determinate",
    )
    complete_progress(
        job_id,
        "Validation complete",
        result_id="result-123",
        redirect_url="/results/result-123",
    )

    payload = get_progress(job_id)
    assert payload["progress"] == 100
    assert payload["status"] == "complete"
    assert payload["phase"] == "complete"
    assert payload["progress_mode"] == "determinate"
    assert payload["result_id"] == "result-123"
    assert payload["redirect_url"] == "/results/result-123"

    clear_progress(job_id)


def test_validate_folder_returns_json_for_ajax_requests(monkeypatch, tmp_path):
    app = _build_app()
    captured = {}

    def fake_launch_validation_job(**kwargs):
        captured.update(kwargs)
        return {
            "job_id": kwargs["job_id"],
            "progress_url": f"/api/progress/{kwargs['job_id']}",
            "status": "started",
        }

    monkeypatch.setattr(
        validation_blueprint_module, "_launch_validation_job", fake_launch_validation_job
    )

    with app.test_client() as client:
        response = client.post(
            "/validate_folder",
            data={
                "folder_path": str(tmp_path),
                "schema_version": "stable",
                "validation_mode": "both",
                "job_id": "job-123",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload == {
        "job_id": "job-123",
        "progress_url": "/api/progress/job-123",
        "status": "started",
    }
    assert captured["dataset_path"] == str(tmp_path)
    assert captured["project_path"] == str(tmp_path)
    assert captured["filename"] == os.path.basename(str(tmp_path))


def test_validate_folder_uses_detected_library_when_no_override_submitted(
    monkeypatch, tmp_path
):
    app = _build_app()
    captured = {}
    project_library = tmp_path / "library"
    project_library.mkdir()

    def fake_launch_validation_job(**kwargs):
        captured.update(kwargs)
        return {
            "job_id": kwargs["job_id"],
            "progress_url": f"/api/progress/{kwargs['job_id']}",
            "status": "started",
        }

    monkeypatch.setattr(
        validation_blueprint_module, "_launch_validation_job", fake_launch_validation_job
    )

    with app.test_client() as client:
        response = client.post(
            "/validate_folder",
            data={
                "folder_path": str(tmp_path),
                "schema_version": "stable",
                "validation_mode": "both",
                "job_id": "job-library-default",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 202
    assert captured["library_path"] == str(project_library)


def test_default_validation_library_path_endpoint_resolves_project_json_context(tmp_path):
    app = _build_app()
    project_root = tmp_path / "validator-project"
    (project_root / "code" / "library").mkdir(parents=True)
    (project_root / "project.json").write_text("{}", encoding="utf-8")

    with app.test_client() as client:
        response = client.get(
            "/api/validation/default-library-path",
            query_string={"project_path": str(project_root / "project.json")},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["default_library_path"] == str(project_root / "code" / "library")
    assert payload["project_path"] == str(project_root / "project.json")


def test_validate_folder_rejects_invalid_library_override(tmp_path):
    app = _build_app()
    invalid_library = tmp_path / "missing-library"

    with app.test_client() as client:
        response = client.post(
            "/validate_folder",
            data={
                "folder_path": str(tmp_path),
                "library_path": str(invalid_library),
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Invalid template library path"


def test_upload_dataset_uses_detected_library_and_project_context(monkeypatch, tmp_path):
    app = _build_app()
    captured = {}
    uploaded_dataset = tmp_path / "uploaded-dataset"
    uploaded_dataset.mkdir()
    (uploaded_dataset / "library").mkdir()

    def fake_process_zip_upload(_file, _temp_dir, _filename):
        return str(uploaded_dataset)

    def fake_launch_validation_job(**kwargs):
        captured.update(kwargs)
        return {
            "job_id": kwargs["job_id"],
            "progress_url": f"/api/progress/{kwargs['job_id']}",
            "status": "started",
        }

    monkeypatch.setattr(
        validation_blueprint_module, "_process_zip_upload", fake_process_zip_upload
    )
    monkeypatch.setattr(
        validation_blueprint_module, "_launch_validation_job", fake_launch_validation_job
    )

    with app.test_client() as client:
        response = client.post(
            "/upload",
            data={
                "dataset": (io.BytesIO(b"placeholder zip bytes"), "dataset.zip"),
                "schema_version": "stable",
                "job_id": "job-upload-default-library",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 202
    assert captured["dataset_path"] == str(uploaded_dataset)
    assert captured["project_path"] == str(uploaded_dataset)
    assert captured["library_path"] == str(uploaded_dataset / "library")


def test_execute_validation_job_builds_redirect_without_server_name(monkeypatch, tmp_path):
    app = _build_app()
    job_id = "job-execute-test"
    clear_progress(job_id)

    monkeypatch.setattr(
        validation_blueprint_module,
        "run_validation",
        lambda *args, **kwargs: ([], {"total_files": 1}),
    )
    monkeypatch.setattr(
        validation_blueprint_module,
        "_build_validation_results_payload",
        lambda **kwargs: {"summary": {"total_files": 1}},
    )
    monkeypatch.setattr(
        validation_blueprint_module,
        "_store_validation_result",
        lambda *args, **kwargs: "result-123",
    )

    result_id = validation_blueprint_module._execute_validation_job(
        app_obj=app,
        job_id=job_id,
        dataset_path=str(tmp_path),
        filename="dataset",
        temp_dir=None,
        schema_version="stable",
        run_bids=False,
        run_prism=True,
        library_path=None,
        show_bids_warnings=False,
        project_path=str(tmp_path),
    )

    payload = get_progress(job_id)
    assert result_id == "result-123"
    assert payload["status"] == "complete"
    assert payload["redirect_url"] == "/results/result-123"

    clear_progress(job_id)


def test_validate_folder_returns_json_error_for_invalid_ajax_path():
    app = _build_app()

    with app.test_client() as client:
        response = client.post(
            "/validate_folder",
            data={"folder_path": "/tmp/does-not-exist-prism-progress"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "Invalid folder path"


def test_revalidate_preserves_hidden_bids_warning_setting(monkeypatch, tmp_path):
    app = _build_app()
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    original_result_id = "result-original"

    monkeypatch.setattr(
        validation_blueprint_module,
        "run_validation",
        lambda *args, **kwargs: ([], {"total_files": 1}),
    )
    monkeypatch.setattr(
        validation_blueprint_module,
        "format_validation_results",
        lambda *args, **kwargs: {
            "summary": {"total_errors": 0},
            "warning_groups": {
                "BIDS-WARN": {
                    "count": 1,
                    "description": "BIDS warning",
                }
            },
            "warnings": [{"code": "BIDS-WARN", "message": "BIDS warning"}],
        },
    )

    with validation_blueprint_module._validation_results_lock:
        validation_blueprint_module._validation_results.clear()
        validation_blueprint_module._validation_results[original_result_id] = {
            "results": {
                "schema_version": "stable",
                "library_path": "",
                "run_bids": True,
                "run_prism": True,
                "show_bids_warnings": False,
                "summary": {"total_errors": 1},
            },
            "dataset_path": str(dataset_dir),
            "temp_dir": None,
            "filename": "dataset",
            "created_at": 0,
        }

    with app.test_client() as client:
        response = client.post(f"/revalidate/{original_result_id}")

    assert response.status_code == 302
    location = response.headers["Location"]
    new_result_id = location.rsplit("/", 1)[-1]

    with validation_blueprint_module._validation_results_lock:
        new_results = validation_blueprint_module._validation_results[new_result_id][
            "results"
        ]
        validation_blueprint_module._validation_results.clear()

    assert new_results["show_bids_warnings"] is False
    assert new_results["bids_warnings_hidden"] == 1
    assert new_results["warning_groups"] == {}
    assert new_results["warnings"] == []