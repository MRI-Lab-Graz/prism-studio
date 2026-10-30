"""GUI wiring for task-free / task-bound physio conversion."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from src.web.blueprints import conversion_physio_handlers as handlers
from src.web.blueprints.conversion import conversion_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(conversion_bp)
    return app.test_client()


@pytest.fixture
def task_folder(tmp_path):
    (tmp_path / "sub-001_task-rest.raw").write_bytes(b"x")
    return tmp_path


def _start(client, folder, **extra):
    data = {"folder_path": str(folder), "modality": "physio", "dry_run": "true", **extra}
    return client.post("/api/batch-convert-start", data=data)


def test_batch_start_without_destination_for_task_files_is_400(client, task_folder):
    resp = _start(client, task_folder)
    assert resp.status_code == 400
    assert "destination" in resp.get_json()["error"]


def test_batch_start_passes_destination(client, task_folder, monkeypatch):
    seen = []

    def fake(*args, **kwargs):
        seen.append(kwargs.get("physio_destination"))
        return SimpleNamespace(
            success_count=0, error_count=0, new_files=0, existing_files=0, converted=[]
        )

    monkeypatch.setattr(handlers, "batch_convert_folder", fake)
    resp = _start(client, task_folder, physio_destination="beh")
    assert resp.status_code == 200
    # the job thread calls the backend too; wait for it
    import time

    for _ in range(50):
        if len(seen) >= 2:
            break
        time.sleep(0.05)
    assert seen and set(seen) == {"beh"}


def test_session_registered_under_target_folder(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        handlers,
        "register_session_in_project",
        lambda *args: calls.append(args),
    )

    def cf(task, folder):
        return SimpleNamespace(success=True, session="1", task=task, target_folder=folder)

    handlers._register_converted_sessions(
        tmp_path, [cf("rest", "beh"), cf(None, "physio")], "ds"
    )
    by_modality = {c[3]: c for c in calls}
    assert by_modality["beh"][1:3] == ("1", ["rest"])
    assert by_modality["physio"][1:3] == ("1", [])


def test_register_session_accepts_empty_task_list(tmp_path):
    import json

    from src.project_registration import register_session_in_project

    (tmp_path / "project.json").write_text(json.dumps({"Name": "p"}), encoding="utf-8")
    register_session_in_project(tmp_path, "1", [], "physio", "ds", "physio")


def test_sync_batch_convert_without_destination_for_task_files_is_400(client, task_folder):
    resp = client.post(
        "/api/batch-convert",
        data={"folder_path": str(task_folder), "modality": "physio", "dry_run": "true"},
    )
    assert resp.status_code == 400
    assert "These physio files have a task and need a destination" in resp.get_json()["error"]


def test_registration_log_has_no_dangling_arrow_without_tasks(monkeypatch, tmp_path):
    monkeypatch.setattr(handlers, "register_session_in_project", lambda *a: None)
    logs = []
    cf = SimpleNamespace(success=True, session="1", task=None, target_folder="physio")
    handlers._register_converted_sessions(
        tmp_path, [cf], "ds", log=lambda msg, level="info": logs.append(msg)
    )
    assert logs == ["Registered in project.json: ses-1 (physio)"]


def _boom(*args, **kwargs):
    raise ValueError("boom: unrelated")


def test_sync_folder_unrelated_value_error_is_500_not_400(client, task_folder, monkeypatch):
    monkeypatch.setattr(handlers, "batch_convert_folder", _boom)
    resp = client.post(
        "/api/batch-convert",
        data={"folder_path": str(task_folder), "modality": "physio", "physio_destination": "beh"},
    )
    assert resp.status_code == 500


def test_sync_upload_unrelated_value_error_is_500_not_400(client, monkeypatch):
    import io

    monkeypatch.setattr(handlers, "batch_convert_folder", _boom)
    resp = client.post(
        "/api/batch-convert",
        data={
            "files[]": (io.BytesIO(b"x"), "sub-001_task-rest.raw"),
            "modality": "physio",
            "physio_destination": "beh",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 500


def test_sync_upload_without_destination_for_task_files_is_400(client):
    import io

    resp = client.post(
        "/api/batch-convert",
        data={"files[]": (io.BytesIO(b"x"), "sub-001_task-rest.raw"), "modality": "physio"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_async_start_uses_public_destination_check(client, task_folder, monkeypatch):
    calls = []
    monkeypatch.setattr(handlers, "check_physio_destination", lambda *a: calls.append(a))
    monkeypatch.setattr(handlers, "batch_convert_folder", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no pre-scan via batch_convert_folder")) if k.get("cancel_check") else SimpleNamespace(success_count=0, error_count=0, new_files=0, existing_files=0, converted=[]))
    resp = _start(client, task_folder)
    assert resp.status_code == 200
    assert calls and calls[0][2] is None
