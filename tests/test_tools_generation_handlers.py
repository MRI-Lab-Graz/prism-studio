from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

from flask import Flask


def _build_app() -> Flask:
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    app = Flask(__name__, root_path=str(app_root))
    app.secret_key = os.urandom(32)
    return app


def test_generate_lss_rejects_null_payload(monkeypatch):
    app = _build_app()
    handlers = importlib.import_module("src.web.blueprints.tools_generation_handlers")

    fake_exporter = types.ModuleType("src.limesurvey_exporter")

    def _generate_lss(*args, **kwargs):
        raise AssertionError("generate_lss should not be called for invalid payload")

    fake_exporter.generate_lss = _generate_lss
    monkeypatch.setitem(sys.modules, "src.limesurvey_exporter", fake_exporter)

    with app.test_request_context(
        "/api/generate-lss",
        method="POST",
        data="null",
        content_type="application/json",
    ):
        response = handlers.handle_generate_lss_endpoint()

    error_response, status_code = response
    assert status_code == 400
    payload = error_response.get_json()
    assert "invalid json payload" in payload["error"].lower()


def test_generate_boilerplate_rejects_null_payload(monkeypatch):
    app = _build_app()
    handlers = importlib.import_module("src.web.blueprints.tools_generation_handlers")

    fake_reporting = types.ModuleType("src.reporting")

    def _generate_methods_text(*args, **kwargs):
        raise AssertionError(
            "generate_methods_text should not be called for invalid payload"
        )

    fake_reporting.generate_methods_text = _generate_methods_text
    monkeypatch.setitem(sys.modules, "src.reporting", fake_reporting)

    with app.test_request_context(
        "/api/generate-boilerplate",
        method="POST",
        data="null",
        content_type="application/json",
    ):
        response = handlers.handle_generate_boilerplate_endpoint()

    error_response, status_code = response
    assert status_code == 400
    payload = error_response.get_json()
    assert "invalid json payload" in payload["error"].lower()


def test_handle_generate_lss_endpoint_cleans_up_temp_file(monkeypatch, tmp_path) -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_generation_handlers")
    exporter = importlib.import_module("src.limesurvey_exporter")

    source_file = tmp_path / "survey-demo.json"
    source_file.write_text("{}", encoding="utf-8")

    created_paths = []

    def fake_generate_lss(file_paths, output_path, **kwargs):
        created_paths.append(output_path)
        Path(output_path).write_text("<xml/>", encoding="utf-8")

    monkeypatch.setattr(exporter, "generate_lss", fake_generate_lss)

    app = Flask(__name__)
    app.add_url_rule(
        "/api/generate-lss",
        view_func=handlers.handle_generate_lss_endpoint,
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post(
            "/api/generate-lss",
            json={"files": [{"path": str(source_file)}], "survey_title": "Demo"},
        )

    assert response.status_code == 200
    assert len(created_paths) == 1
    assert not Path(created_paths[0]).exists()
