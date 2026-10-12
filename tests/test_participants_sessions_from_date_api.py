"""GUI endpoints: the sessions-from-date checkbox only passes the option to the backend."""

import io
import time

import pytest
from flask import Flask

from src.web.blueprints import conversion_participants_blueprint as participants_module

REPEATED_CSV = (
    "token,startdate,submitdate,age\n"
    "a,2026-09-01 10:00:00,x,31\n"
    "a,2026-03-01 10:00:00,x,30\n"
    "b,2026-03-02 10:00:00,x,40\n"
)


@pytest.fixture
def client(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(
        '{"StudyDesign": {"Timepoints": "single"}}', encoding="utf-8"
    )
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(participants_module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["current_project_path"] = str(project)
    client.project = project
    return client


def _upload(**fields):
    return {
        "mode": "file",
        "file": (io.BytesIO(REPEATED_CSV.encode()), "data.csv"),
        "id_column": "token",
        **fields,
    }


def test_preview_with_the_checkbox_offers_the_dated_sessions(client):
    response = client.post(
        "/api/participants-preview",
        data=_upload(sessions_from_date="startdate"),
        content_type="multipart/form-data",
    )

    assert {"column": "session", "values": ["1", "2"]} in response.get_json()["session_candidates"]


def test_convert_with_the_checkbox_writes_the_chosen_dated_session(client):
    start = client.post(
        "/api/participants-convert-start",
        data=_upload(sessions_from_date="startdate", session_column="session", session_value="1"),
        content_type="multipart/form-data",
    )
    assert start.status_code == 200, start.get_json()
    job_id = start.get_json()["job_id"]
    deadline = time.monotonic() + 30
    while True:
        status = client.get(f"/api/participants-convert-status/{job_id}").get_json()
        if status["done"] or time.monotonic() > deadline:
            break

    assert status.get("success"), status
    header, *rows = [
        line.split("\t") for line in (client.project / "participants.tsv").read_text().splitlines()
    ]
    age = header.index("age")
    assert [(row[0], row[age]) for row in rows] == [("sub-a", "30"), ("sub-b", "40")]


def test_merge_with_the_checkbox_asks_for_a_session_choice(client):
    (client.project / "participants.tsv").write_text(
        "participant_id\tage\nsub-b\t40\n", encoding="utf-8"
    )
    response = client.post(
        "/api/participants-merge",
        data=_upload(sessions_from_date="startdate"),
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert payload["session_resolution_column"] == "session"
    assert payload["session_resolution_required"] is True
