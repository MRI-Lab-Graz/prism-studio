from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path

from flask import Flask
import pytest


def _build_app_and_handlers():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    biometrics = importlib.import_module("src.web.blueprints.conversion_biometrics_handlers")
    survey = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
    physio = importlib.import_module("src.web.blueprints.conversion_physio_handlers")
    environment = importlib.import_module("src.web.blueprints.conversion_environment_handlers")

    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = "test-secret"
    app.add_url_rule(
        "/api/biometrics-convert",
        view_func=biometrics.api_biometrics_convert,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/survey-convert-validate",
        view_func=survey.api_survey_convert_validate,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/batch-convert-start",
        view_func=physio.api_batch_convert_start,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/environment-convert-start",
        view_func=environment.api_environment_convert_start,
        methods=["POST"],
    )
    return app, biometrics, survey, physio, environment


def test_biometrics_convert_rejects_stale_project_path(tmp_path, monkeypatch):
    app, biometrics, _survey, _physio, _environment = _build_app_and_handlers()
    library_root = tmp_path / "library"
    biometrics_dir = library_root / "biometrics"
    biometrics_dir.mkdir(parents=True, exist_ok=True)
    (biometrics_dir / "biometrics-grip.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(biometrics, "resolve_effective_library_path", lambda: library_root)

    def _unexpected_convert(**_kwargs):
        raise AssertionError("biometrics converter should not run with a stale project path")

    monkeypatch.setattr(
        biometrics,
        "convert_biometrics_table_to_prism_dataset",
        _unexpected_convert,
    )

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path / "missing-project")

        response = client.post(
            "/api/biometrics-convert",
            data={
                "session": "1",
                "validate": "true",
                "tasks[]": ["grip"],
                "data": (io.BytesIO(b"participant_id,value\nsub-01,1\n"), "biometrics.csv"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "no longer exists" in payload["error"].lower()


def test_survey_convert_rejects_stale_project_path(tmp_path, monkeypatch):
    app, _biometrics, survey, _physio, _environment = _build_app_and_handlers()
    library_root = tmp_path / "library"
    survey_dir = library_root / "survey"
    survey_dir.mkdir(parents=True, exist_ok=True)
    (survey_dir / "survey-demo.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(survey, "_resolve_effective_library_path", lambda: library_root)

    def _unexpected_convert(**_kwargs):
        raise AssertionError("survey converter should not run with a stale project path")

    monkeypatch.setattr(survey, "convert_survey_xlsx_to_prism_dataset", _unexpected_convert)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path / "missing-project")

        response = client.post(
            "/api/survey-convert-validate",
            data={
                "id_column": "participant_id",
                "excel": (
                    io.BytesIO(b"participant_id,score\nsub-01,1\n"),
                    "survey.csv",
                ),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "no longer exists" in payload["error"].lower()


def test_batch_convert_start_rejects_stale_project_path(tmp_path):
    app, _biometrics, _survey, _physio, _environment = _build_app_and_handlers()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path / "missing-project")

        response = client.post(
            "/api/batch-convert-start",
            data={
                "modality": "physio",
                "save_to_project": "true",
                "dry_run": "false",
                "files": (
                    io.BytesIO(b"raw-bytes"),
                    "sub-01_task-rest_physio.raw",
                ),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "no longer exists" in payload["error"].lower()


def test_environment_convert_start_rejects_stale_project_path(tmp_path):
    app, _biometrics, _survey, _physio, _environment = _build_app_and_handlers()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(tmp_path / "missing-project")

        response = client.post(
            "/api/environment-convert-start",
            data={
                "file": (
                    io.BytesIO(
                        b"timestamp,participant_id,session\n2025-01-15 10:30:00,01,01\n"
                    ),
                    "environment.csv",
                ),
                "separator": "comma",
                "timestamp_col": "timestamp",
                "participant_col": "participant_id",
                "session_col": "session",
                "lat": "47.0667",
                "lon": "15.45",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "no longer exists" in payload["error"].lower()


def test_environment_conversion_rechecks_project_path_before_write(
    tmp_path, monkeypatch
):
    _app, _biometrics, _survey, _physio, environment = _build_app_and_handlers()

    input_path = tmp_path / "environment.csv"
    input_path.write_text(
        "timestamp,participant_id,session\n2025-01-15 10:30:00,01,01\n",
        encoding="utf-8",
    )

    missing_project_path = tmp_path / "missing-project"

    monkeypatch.setattr(
        environment,
        "_fetch_environment_day",
        lambda *args, **kwargs: ({"weather": {}, "air": {}, "pollen": {}}, []),
    )
    monkeypatch.setattr(
        environment,
        "_save_environment_provider_cache",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(FileNotFoundError, match="no longer exists"):
        environment._perform_environment_conversion(
            input_path=input_path,
            filename="environment.csv",
            suffix=".csv",
            separator_option="comma",
            timestamp_col="timestamp",
            participant_col="participant_id",
            participant_override=None,
            session_col="session",
            session_override=None,
            location_col=None,
            lat_col=None,
            lon_col=None,
            location_label_override="",
            lat_manual=47.0667,
            lon_manual=15.45,
            project_path=str(missing_project_path),
            pilot_random_subject=False,
            log_callback=lambda *_args, **_kwargs: None,
        )