import importlib
import io

from flask import Flask

from test_limesurvey_e2e import LSS_XML


def test_handle_limesurvey_to_prism_combined_mode_from_lss_upload() -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_limesurvey_handlers")

    app = Flask(__name__)
    app.add_url_rule(
        "/api/limesurvey-to-prism",
        view_func=handlers.handle_limesurvey_to_prism,
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post(
            "/api/limesurvey-to-prism",
            data={
                "file": (io.BytesIO(LSS_XML.encode("utf-8")), "e2e_test_survey.lss"),
                "mode": "combined",
                "task_name": "wellbeing",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get("success") is True
    assert payload.get("mode") == "combined"
    assert payload.get("question_count", 0) >= 1
    assert "error" not in payload


def test_handle_limesurvey_to_prism_rejects_unsupported_extension() -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_limesurvey_handlers")

    app = Flask(__name__)
    app.add_url_rule(
        "/api/limesurvey-to-prism",
        view_func=handlers.handle_limesurvey_to_prism,
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post(
            "/api/limesurvey-to-prism",
            data={"file": (io.BytesIO(b"not a survey"), "notes.txt")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
