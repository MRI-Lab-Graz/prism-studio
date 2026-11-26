import importlib
import io

import openpyxl
import pytest
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


def test_handle_limesurvey_to_prism_no_longer_offers_one_template_per_question() -> None:
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
                "mode": "questions",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid mode 'questions'. Use: combined or groups"


def test_excel_upload_logs_what_the_import_loses() -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_limesurvey_handlers")
    app = Flask(__name__)
    app.add_url_rule(
        "/api/limesurvey-to-prism",
        view_func=handlers.handle_limesurvey_to_prism,
        methods=["POST"],
    )
    wb = openpyxl.Workbook()
    wb.active.append(["Variable name", "Description_de", "Scaling"])
    wb.active.append(["lossy_1", "Frage", "0=ja;1=ja"])
    codebook = io.BytesIO()
    wb.save(codebook)
    codebook.seek(0)

    body = (
        app.test_client()
        .post(
            "/api/limesurvey-to-prism",
            data={"file": (codebook, "c.xlsx")},
            content_type="multipart/form-data",
        )
        .get_json()
    )

    assert {
        "message": "lossy_1: several codes have the same label 'ja'",
        "type": "warning",
    } in body["log"], body


@pytest.mark.parametrize("name,sep", [("c.csv", ","), ("c.tsv", "\t"), ("C.CSV", ",")])
def test_text_codebook_upload_is_imported(name, sep) -> None:
    handlers = importlib.import_module("src.web.blueprints.tools_limesurvey_handlers")
    app = Flask(__name__)
    app.add_url_rule(
        "/api/limesurvey-to-prism",
        view_func=handlers.handle_limesurvey_to_prism,
        methods=["POST"],
    )
    rows = [["Variable name", "Description_de", "Scaling"], ["abc_1", "Frage", "0=ja"]]
    content = "\n".join(sep.join(row) for row in rows).encode("utf-8")

    response = app.test_client().post(
        "/api/limesurvey-to-prism",
        data={"file": (io.BytesIO(content), name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200, response.get_json()
    assert "abc_1" in response.get_data(as_text=True)
