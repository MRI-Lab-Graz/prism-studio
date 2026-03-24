from __future__ import annotations

import io
import sys
from pathlib import Path

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = PROJECT_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.tools import tools_bp


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"  # pragma: allowlist secret
    app.register_blueprint(tools_bp)
    return app


def test_wide_to_long_preview_executes_backend_command():
    app = _build_app()
    client = app.test_client()

    csv_bytes = b"participant_id,T1_score,T2_score\nsub-01,1,2\nsub-02,3,4\n"

    response = client.post(
        "/api/file-management/wide-to-long-preview",
        data={
            "data": (io.BytesIO(csv_bytes), "survey.csv"),
            "session_column": "session",
            "session_indicators": "T1_,T2_",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["can_convert"] is True
    assert body["column_rename_preview"][0]["output_column"] == "score"


def test_wide_to_long_preview_handles_stdout_with_non_json_prefix():
    app = _build_app()
    client = app.test_client()

    csv_bytes = b"participant_id,ADS01_pre,ADS01_post\nsub-01,1,2\n"

    response = client.post(
        "/api/file-management/wide-to-long-preview",
        data={
            "data": (io.BytesIO(csv_bytes), "survey.csv"),
            "session_column": "session",
            "session_indicators": "_pre,_post",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["can_convert"] is True
    assert body["column_rename_preview"][0]["output_column"] == "ADS01"


def test_wide_to_long_convert_executes_backend_command_and_returns_file():
    app = _build_app()
    client = app.test_client()

    csv_bytes = b"participant_id,T1_score,T2_score\nsub-01,1,2\n"

    response = client.post(
        "/api/file-management/wide-to-long",
        data={
            "data": (io.BytesIO(csv_bytes), "survey.csv"),
            "session_column": "session",
            "session_indicators": "T1_,T2_",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    decoded = response.data.decode("utf-8")
    assert "participant_id,score,session" in decoded
    assert "sub-01,1,T1_" in decoded
    assert "sub-01,2,T2_" in decoded
    disposition = response.headers.get("Content-Disposition", "")
    assert "survey_long.csv" in disposition
