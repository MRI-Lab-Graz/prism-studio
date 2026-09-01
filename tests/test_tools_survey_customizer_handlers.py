import importlib
import json
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


def test_handle_survey_customizer_load_builds_groups_from_template(tmp_path) -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )
    info_helpers = importlib.import_module(
        "src.web.blueprints.tools_template_info_helpers"
    )

    template_path = tmp_path / "survey-demo.json"
    template_path.write_text(
        json.dumps(
            {
                "Study": {"OriginalName": "Demo Survey"},
                "Q1": {
                    "Description": {"en": "How are you?"},
                    "Levels": {"1": "Bad", "2": "Good"},
                    "Mandatory": True,
                },
            }
        ),
        encoding="utf-8",
    )

    app = Flask(__name__)
    with app.app_context():
        response = handlers.handle_survey_customizer_load(
            data={"files": [{"path": str(template_path)}]},
            detect_languages_from_template=info_helpers.detect_languages_from_template,
        )
        payload = response.get_json()

    assert response.status_code == 200
    assert payload["totalQuestions"] == 1
    assert payload["groups"][0]["name"] == "Demo Survey"
    assert payload["groups"][0]["questions"][0]["questionCode"] == "Q1"
    assert payload["groups"][0]["questions"][0]["description"] == "How are you?"


def test_handle_survey_customizer_load_rejects_empty_files() -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    app = Flask(__name__)
    with app.app_context():
        response, status = handlers.handle_survey_customizer_load(
            data={"files": []},
            detect_languages_from_template=lambda template: set(),
        )
        payload = response.get_json()

    assert status == 400
    assert payload["error"] == "No files provided"
