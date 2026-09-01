import importlib
from pathlib import Path

from flask import Flask


def test_handle_survey_customizer_export_cleans_up_temp_file(monkeypatch) -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )
    exporter = importlib.import_module("src.limesurvey_exporter")

    created_paths = []

    def fake_generate_lss_from_customization(*, output_path, **kwargs):
        created_paths.append(output_path)
        Path(output_path).write_text("<xml/>", encoding="utf-8")

    monkeypatch.setattr(
        exporter,
        "generate_lss_from_customization",
        fake_generate_lss_from_customization,
    )

    app = Flask(__name__)
    app.add_url_rule(
        "/api/survey-customizer/export",
        view_func=lambda: handlers.handle_survey_customizer_export(
            data={
                "survey": {"title": "Demo Survey", "language": "en"},
                "groups": [{"id": "g1"}],
                "exportFormat": "limesurvey",
            },
            project_path=None,
        ),
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post("/api/survey-customizer/export")

    assert response.status_code == 200
    assert len(created_paths) == 1
    assert not Path(created_paths[0]).exists()
