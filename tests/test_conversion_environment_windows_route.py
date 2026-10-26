"""Environment converter routes: time windows are VAR:DURATION:STAT strings checked by parse_window."""

import io
from unittest.mock import patch

import pytest
from flask import Flask

from src.environment_windows import WINDOW_COLUMNS, STATISTICS, window_column_name
from src.web.blueprints import conversion_environment_handlers as env
from src.web.blueprints.conversion import conversion_bp

CSV = b"timestamp,participant_id,session\n2025-01-15 10:30:00,01,01\n"


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = "t"  # pragma: allowlist secret
    app.register_blueprint(conversion_bp)
    c = app.test_client()
    with c.session_transaction() as s:
        s["current_project_path"] = str(tmp_path)
    return c


def _start(client, windows):
    return client.post(
        "/api/environment-convert-start",
        data={
            "file": (io.BytesIO(CSV), "environment.csv"),
            "separator": "comma", "timestamp_col": "timestamp", "participant_col": "participant_id",
            "session_col": "session", "lat": "47.0667", "lon": "15.45", "windows": windows,
        },
        content_type="multipart/form-data",
    )


class _Inline:
    def __init__(self, target, args=(), **_):
        self.run = lambda: target(*args)

    def start(self):
        self.run()


def test_route_passes_windows(client):
    seen = {}

    def fake(**kw):
        seen["windows"] = kw["windows"]
        return {"row_count": 1, "window_problems": [{"column": "temp_c_max_p3d", "empty_rows": 2, "partial_rows": 1}]}

    with patch.object(env.threading, "Thread", _Inline), patch.object(env, "_perform_environment_conversion", fake):
        response = _start(client, ["temp_c:P3D:max"])
        assert response.status_code == 200
        status = client.get(f"/api/environment-convert-status/{response.get_json()['job_id']}").get_json()
    assert [window_column_name(w) for w in seen["windows"]] == ["temp_c_max_p3d"]
    assert status["result"]["window_problems"] == [{"column": "temp_c_max_p3d", "empty_rows": 2, "partial_rows": 1}]


def test_route_bad_window_message(client):
    from src.environment_windows import parse_window

    with pytest.raises(ValueError) as expected:
        parse_window("temp_c:3d:max")
    response = _start(client, ["temp_c:3d:max"])
    assert response.status_code == 400
    assert response.get_json()["error"] == str(expected.value)


def test_window_options_route_lists_the_backend_columns(client):
    payload = client.get("/api/environment-window-options").get_json()
    assert payload == {"columns": list(WINDOW_COLUMNS), "statistics": list(STATISTICS)}
