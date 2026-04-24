from __future__ import annotations

import importlib
import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


def _build_app_and_handlers():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    handlers = importlib.import_module("src.web.blueprints.conversion_physio_handlers")
    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)
    app.add_url_rule(
        "/api/physio-rename",
        view_func=handlers.api_physio_rename,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/batch-convert",
        view_func=handlers.api_batch_convert,
        methods=["POST"],
    )
    return app, handlers


def test_physio_rename_saves_flat_rawdata_copy_under_project_rawdata(tmp_path):
    app, _handlers = _build_app_and_handlers()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/physio-rename",
            data={
                "pattern": "^.*$",
                "replacement": "sub-01_task-rest_physio.edf",
                "save_to_project": "true",
                "skip_zip": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "modality": "physio",
                "files": (io.BytesIO(b"renamed-bytes"), "source.edf"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert payload["project_output_root"] == str(tmp_path)
    assert (
        payload["project_output_path"] == "rawdata/physio/sub-01_task-rest_physio.edf"
    )
    assert payload["project_output_paths"] == [
        "rawdata/physio/sub-01_task-rest_physio.edf"
    ]

    saved_path = tmp_path / "rawdata" / "physio" / "sub-01_task-rest_physio.edf"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"renamed-bytes"
    assert not (tmp_path / "sub-01_task-rest_physio.edf").exists()


def test_physio_rename_accepts_server_file_paths_for_project_copy(tmp_path):
    app, _handlers = _build_app_and_handlers()
    source_dir = tmp_path / "server-source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "sub-01_task-rest_physio.edf"
    source_file.write_bytes(b"server-renamed-bytes")

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/physio-rename",
            data={
                "pattern": "^.*$",
                "replacement": "sub-01_task-rest_physio.edf",
                "save_to_project": "true",
                "skip_zip": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "modality": "physio",
                "server_file_paths": str(source_file),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert (
        payload["project_output_path"] == "rawdata/physio/sub-01_task-rest_physio.edf"
    )

    saved_path = tmp_path / "rawdata" / "physio" / "sub-01_task-rest_physio.edf"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"server-renamed-bytes"


def test_batch_convert_folder_path_rejects_stale_project_path(tmp_path):
    app, _handlers = _build_app_and_handlers()
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path / "missing-project")

        response = client.post(
            "/api/batch-convert",
            data={
                "modality": "physio",
                "save_to_project": "true",
                "dest_root": "rawdata",
                "folder_path": str(source_dir),
            },
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "no longer exists" in payload["error"].lower()


def test_physio_rename_rejects_stale_project_path(tmp_path):
    app, _handlers = _build_app_and_handlers()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path / "missing-project")

        response = client.post(
            "/api/physio-rename",
            data={
                "pattern": "^.*$",
                "replacement": "sub-01_task-rest_physio.edf",
                "save_to_project": "true",
                "skip_zip": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "modality": "physio",
                "files": (io.BytesIO(b"renamed-bytes"), "source.edf"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "no longer exists" in payload["error"].lower()


def test_physio_rename_rewrites_subject_to_last_three_digits_for_project_copy(tmp_path):
    app, _handlers = _build_app_and_handlers()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/physio-rename",
            data={
                "pattern": "^.*$",
                "replacement": "sub-1293167_task-rest_physio.edf",
                "save_to_project": "true",
                "skip_zip": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "subject_rewrite_mode": "last3",
                "modality": "physio",
                "files": (io.BytesIO(b"renamed-bytes"), "source.edf"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert (
        payload["project_output_path"]
        == "rawdata/physio/sub-167_task-rest_physio.edf"
    )

    saved_path = tmp_path / "rawdata" / "physio" / "sub-167_task-rest_physio.edf"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"renamed-bytes"
    assert not (tmp_path / "rawdata" / "physio" / "sub-1293167_task-rest_physio.edf").exists()


def test_check_sourcedata_physio_accepts_project_json_session_value(tmp_path):
    app, handlers = _build_app_and_handlers()
    project_json = tmp_path / "project.json"
    project_json.write_text("{}", encoding="utf-8")
    sourcedata_physio = tmp_path / "sourcedata" / "physio"
    sourcedata_physio.mkdir(parents=True, exist_ok=True)
    (sourcedata_physio / "signal.raw").write_bytes(b"raw-bytes")

    app.add_url_rule(
        "/api/check-sourcedata-physio",
        view_func=handlers.check_sourcedata_physio,
        methods=["GET"],
    )

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(project_json)

        response = client.get("/api/check-sourcedata-physio")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["exists"] is True
    assert payload["path"] == str(sourcedata_physio)


def test_physio_rename_rejects_flat_copy_into_prism_root(tmp_path):
    app, _handlers = _build_app_and_handlers()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/physio-rename",
            data={
                "pattern": "^.*$",
                "replacement": "sub-01_task-rest_physio.edf",
                "save_to_project": "true",
                "skip_zip": "true",
                "dest_root": "prism",
                "flat_structure": "true",
                "modality": "physio",
                "files": (io.BytesIO(b"renamed-bytes"), "source.edf"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert (
        payload["error"]
        == "Flat output cannot be copied into the PRISM root. Enable PRISM folders or copy to rawdata/sourcedata instead."
    )


def test_batch_convert_saves_flat_rawdata_copy_under_project_rawdata(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    def fake_batch_convert_folder(_source_dir, output_dir, **_kwargs):
        output_path = (
            Path(output_dir)
            / "sub-01"
            / "ses-01"
            / "physio"
            / "sub-01_ses-01_task-rest_physio.edf"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"converted-bytes")
        return SimpleNamespace(
            success_count=1,
            error_count=0,
            new_files=1,
            existing_files=0,
            conflicts=[],
            converted=[],
        )

    monkeypatch.setattr(handlers, "batch_convert_folder", fake_batch_convert_folder)
    monkeypatch.setattr(
        handlers,
        "parse_bids_filename",
        lambda filename: {"sub": "sub-01"} if filename.startswith("sub-01") else None,
    )
    monkeypatch.setattr(
        handlers,
        "create_dataset_description",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        handlers,
        "register_session_in_project",
        lambda *args, **kwargs: None,
    )

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/batch-convert",
            data={
                "modality": "physio",
                "save_to_project": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "files": (
                    io.BytesIO(b"source-bytes"),
                    "sub-01_task-rest_physio.edf",
                ),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert payload["project_output_root"] == str(tmp_path)
    assert (
        payload["project_output_path"]
        == "rawdata/physio/sub-01_ses-01_task-rest_physio.edf"
    )
    assert payload["project_output_paths"] == [
        "rawdata/physio/sub-01_ses-01_task-rest_physio.edf"
    ]

    saved_path = tmp_path / "rawdata" / "physio" / "sub-01_ses-01_task-rest_physio.edf"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"converted-bytes"
    assert not (
        tmp_path / "sub-01" / "ses-01" / "physio" / "sub-01_ses-01_task-rest_physio.edf"
    ).exists()


def test_batch_convert_accepts_server_file_paths_for_project_copy(tmp_path, monkeypatch):
    app, handlers = _build_app_and_handlers()

    server_source_dir = tmp_path / "server-source"
    server_source_dir.mkdir(parents=True, exist_ok=True)
    server_source_file = server_source_dir / "sub-01_task-rest_physio.edf"
    server_source_file.write_bytes(b"server-source-bytes")

    def fake_batch_convert_folder(_source_dir, output_dir, **_kwargs):
        output_path = (
            Path(output_dir)
            / "sub-01"
            / "ses-01"
            / "physio"
            / "sub-01_ses-01_task-rest_physio.edf"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"converted-bytes")
        return SimpleNamespace(
            success_count=1,
            error_count=0,
            new_files=1,
            existing_files=0,
            conflicts=[],
            converted=[],
        )

    monkeypatch.setattr(handlers, "batch_convert_folder", fake_batch_convert_folder)
    monkeypatch.setattr(
        handlers,
        "parse_bids_filename",
        lambda filename: {"sub": "sub-01"} if filename.startswith("sub-01") else None,
    )
    monkeypatch.setattr(
        handlers,
        "create_dataset_description",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        handlers,
        "register_session_in_project",
        lambda *args, **kwargs: None,
    )

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/batch-convert",
            data={
                "modality": "physio",
                "save_to_project": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "server_file_paths": str(server_source_file),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert payload["project_output_root"] == str(tmp_path)
    assert (
        payload["project_output_path"]
        == "rawdata/physio/sub-01_ses-01_task-rest_physio.edf"
    )

    saved_path = tmp_path / "rawdata" / "physio" / "sub-01_ses-01_task-rest_physio.edf"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"converted-bytes"


def test_batch_convert_rewrites_subject_to_last_three_digits_for_project_copy(
    tmp_path, monkeypatch
):
    app, handlers = _build_app_and_handlers()

    def fake_batch_convert_folder(_source_dir, output_dir, **_kwargs):
        output_path = (
            Path(output_dir)
            / "sub-1293167"
            / "ses-01"
            / "physio"
            / "sub-1293167_ses-01_task-rest_physio.edf"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"converted-bytes")
        return SimpleNamespace(
            success_count=1,
            error_count=0,
            new_files=1,
            existing_files=0,
            conflicts=[],
            converted=[],
        )

    monkeypatch.setattr(handlers, "batch_convert_folder", fake_batch_convert_folder)
    monkeypatch.setattr(
        handlers,
        "parse_bids_filename",
        lambda filename: {"sub": "sub-1293167"}
        if filename.startswith("sub-1293167")
        else ({"sub": "sub-167"} if filename.startswith("sub-167") else None),
    )
    monkeypatch.setattr(
        handlers,
        "create_dataset_description",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        handlers,
        "register_session_in_project",
        lambda *args, **kwargs: None,
    )

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path)

        response = client.post(
            "/api/batch-convert",
            data={
                "modality": "physio",
                "save_to_project": "true",
                "dest_root": "prism",
                "flat_structure": "false",
                "subject_rewrite_mode": "last3",
                "files": (
                    io.BytesIO(b"source-bytes"),
                    "sub-1293167_task-rest_physio.edf",
                ),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert (
        payload["project_output_path"]
        == "sub-167/ses-01/physio/sub-167_ses-01_task-rest_physio.edf"
    )
    saved_path = (
        tmp_path
        / "sub-167"
        / "ses-01"
        / "physio"
        / "sub-167_ses-01_task-rest_physio.edf"
    )
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"converted-bytes"
    assert not (
        tmp_path
        / "sub-1293167"
        / "ses-01"
        / "physio"
        / "sub-1293167_ses-01_task-rest_physio.edf"
    ).exists()


def test_batch_convert_can_target_explicit_project_path(tmp_path, monkeypatch):
    app, handlers = _build_app_and_handlers()

    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    primary_project.mkdir()
    target_project.mkdir()

    def fake_batch_convert_folder(_source_dir, output_dir, **_kwargs):
        output_path = (
            Path(output_dir)
            / "sub-01"
            / "ses-01"
            / "physio"
            / "sub-01_ses-01_task-rest_physio.edf"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"converted-bytes")
        return SimpleNamespace(
            success_count=1,
            error_count=0,
            new_files=1,
            existing_files=0,
            conflicts=[],
            converted=[],
        )

    monkeypatch.setattr(handlers, "batch_convert_folder", fake_batch_convert_folder)
    monkeypatch.setattr(
        handlers,
        "parse_bids_filename",
        lambda filename: {"sub": "sub-01"} if filename.startswith("sub-01") else None,
    )
    monkeypatch.setattr(
        handlers,
        "create_dataset_description",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        handlers,
        "register_session_in_project",
        lambda *args, **kwargs: None,
    )

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(primary_project)

        response = client.post(
            "/api/batch-convert",
            data={
                "modality": "physio",
                "save_to_project": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "project_path": str(target_project),
                "files": (
                    io.BytesIO(b"source-bytes"),
                    "sub-01_task-rest_physio.edf",
                ),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert payload["project_output_root"] == str(target_project)
    saved_path = (
        target_project / "rawdata" / "physio" / "sub-01_ses-01_task-rest_physio.edf"
    )
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"converted-bytes"
    assert not (
        primary_project / "rawdata" / "physio" / "sub-01_ses-01_task-rest_physio.edf"
    ).exists()


def test_physio_rename_can_target_explicit_project_path(tmp_path):
    app, _handlers = _build_app_and_handlers()

    primary_project = tmp_path / "primary"
    target_project = tmp_path / "target"
    primary_project.mkdir()
    target_project.mkdir()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(primary_project)

        response = client.post(
            "/api/physio-rename",
            data={
                "pattern": "^.*$",
                "replacement": "sub-01_task-rest_physio.edf",
                "save_to_project": "true",
                "skip_zip": "true",
                "dest_root": "rawdata",
                "flat_structure": "true",
                "project_path": str(target_project),
                "modality": "physio",
                "files": (io.BytesIO(b"renamed-bytes"), "source.edf"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_saved"] is True
    assert payload["project_output_root"] == str(target_project)
    saved_path = target_project / "rawdata" / "physio" / "sub-01_task-rest_physio.edf"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"renamed-bytes"
    assert not (
        primary_project / "rawdata" / "physio" / "sub-01_task-rest_physio.edf"
    ).exists()
