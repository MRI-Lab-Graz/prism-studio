from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = PROJECT_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.tools import tools_bp


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(tools_bp)
    return app


def test_wide_to_long_preview_executes_backend_command():
    app = _build_app()
    client = app.test_client()

    payload = {
        "filename": "survey.xlsx",
        "detected_indicators": ["T1_", "T2_", "T3_"],
        "detected_prefixes": ["T1_", "T2_", "T3_"],
        "can_convert": True,
        "column_rename_preview": [{"column": "T1_score", "output_column": "score", "indicator": "T1_"}],
        "ambiguous_columns": [],
        "rows_total": 2,
        "rows_shown": 2,
        "columns": ["participant_id", "score", "session"],
        "rows": [
            {"participant_id": "sub-01", "score": "1", "session": "T1_"},
            {"participant_id": "sub-01", "score": "2", "session": "T2_"},
        ],
    }

    with patch("src.web.blueprints.tools.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(payload)
        mock_run.return_value.stderr = ""

        response = client.post(
            "/api/file-management/wide-to-long-preview",
            data={
                "data": (io.BytesIO(b"dummy"), "survey.xlsx"),
                "session_column": "session",
                "session_indicators": "T1_,T2_,T3_",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["can_convert"] is True
    assert body["column_rename_preview"][0]["output_column"] == "score"

    command = mock_run.call_args.args[0]
    assert command[1] == "prism.py"
    assert command[2] == "wide-to-long"
    assert "--json" in command
    assert "--inspect-only" in command


def test_wide_to_long_convert_executes_backend_command_and_returns_file():
    app = _build_app()
    client = app.test_client()

    payload = {
        "filename": "survey.xlsx",
        "detected_indicators": ["T1_", "T2_"],
        "detected_prefixes": ["T1_", "T2_"],
        "can_convert": True,
        "column_rename_preview": [],
        "ambiguous_columns": [],
        "rows_total": 2,
        "rows_shown": 2,
        "columns": ["participant_id", "score", "session"],
        "rows": [],
        "output_path": "ignored.csv",
    }
    output_csv = b"participant_id,score,session\nsub-01,1,T1_\nsub-01,2,T2_\n"

    def _fake_run(command, capture_output, text, cwd):
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_bytes(output_csv)

        class _Result:
            returncode = 0
            stdout = json.dumps(payload)
            stderr = ""

        return _Result()

    with patch("src.web.blueprints.tools.subprocess.run", side_effect=_fake_run) as mock_run:
        response = client.post(
            "/api/file-management/wide-to-long",
            data={
                "data": (io.BytesIO(b"dummy"), "survey.xlsx"),
                "session_column": "session",
                "session_indicators": "T1_,T2_",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    assert response.data == output_csv
    disposition = response.headers.get("Content-Disposition", "")
    assert "survey_long.csv" in disposition

    command = mock_run.call_args.args[0]
    assert command[1] == "prism.py"
    assert command[2] == "wide-to-long"
    assert "--json" in command
    assert "--inspect-only" not in command