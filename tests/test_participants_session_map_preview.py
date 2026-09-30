"""The participants preview tells the page which chosen session still needs a map entry."""

import io
import json

import pytest
from flask import Flask

from src.session_map import save_session_map
from src.web.blueprints import conversion_participants_blueprint as participants_module

CSV = "participant_id,session,age\n1,pre,30\n1,post,31\n2,pre,40\n2,post,41\n"


def make_client(tmp_path, project_json):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(participants_module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["current_project_path"] = str(project)
    client.project = project
    return client


def preview(client, **fields):
    return client.post(
        "/api/participants-preview",
        data={
            "mode": "file",
            "file": (io.BytesIO(CSV.encode()), "data.csv"),
            "id_column": "participant_id",
            **fields,
        },
        content_type="multipart/form-data",
    )


@pytest.fixture
def multiple(tmp_path):
    return make_client(tmp_path, {"StudyDesign": {"Timepoints": "multiple"}})


def test_the_chosen_unmapped_session_is_reported(multiple):
    body = preview(multiple, session_column="session", session_value="pre").get_json()
    assert body["unmapped_session_labels"] == ["pre"]


def test_a_mapped_session_is_not_reported(multiple):
    save_session_map(multiple.project, {"pre": "1"})
    body = preview(multiple, session_column="session", session_value="pre").get_json()
    assert body["unmapped_session_labels"] == []


def test_only_the_chosen_session_is_asked_for(multiple):
    save_session_map(multiple.project, {"post": "2"})
    body = preview(multiple, session_column="session", session_value="pre").get_json()
    assert body["unmapped_session_labels"] == ["pre"]  # 'post' is not being imported


def test_no_chosen_session_reports_nothing(multiple):
    assert preview(multiple).get_json()["unmapped_session_labels"] == []


def test_single_timepoint_project_reports_nothing(tmp_path):
    client = make_client(tmp_path, {"StudyDesign": {"Timepoints": "single"}})
    body = preview(client, session_column="session", session_value="pre").get_json()
    assert body["unmapped_session_labels"] == []


def test_undeclared_project_with_a_chosen_session_says_to_declare_it(tmp_path):
    client = make_client(tmp_path, {})
    response = preview(client, session_column="session", session_value="pre")
    assert response.status_code == 400
    assert "Timepoints" in response.get_json()["error"]
