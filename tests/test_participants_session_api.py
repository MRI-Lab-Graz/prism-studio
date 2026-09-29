"""Longitudinal files through the participants preview/convert endpoints."""

import io
import time

import pytest
from flask import Flask

from src.web.blueprints import conversion_participants_blueprint as participants_module

LONGITUDINAL_CSV = (
    "participant_id,session,age,sex\n"
    "1,baseline,30,2\n"
    "1,followup,31,2\n"
    "2,baseline,40,1\n"
    "2,followup,41,1\n"
)
CROSS_SECTIONAL_CSV = "participant_id,age,sex\n1,30,2\n2,40,1\n"


@pytest.fixture
def client(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(participants_module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["current_project_path"] = str(project)
    client.project = project
    return client


def _upload(csv_text, **fields):
    return {
        "mode": "file",
        "file": (io.BytesIO(csv_text.encode()), "data.csv"),
        "id_column": "participant_id",
        **fields,
    }


def _convert(client, **fields):
    start = client.post(
        "/api/participants-convert-start",
        data=_upload(LONGITUDINAL_CSV, **fields),
        content_type="multipart/form-data",
    )
    if start.status_code != 200:
        return start.status_code, start.get_json()
    job_id = start.get_json()["job_id"]
    deadline = time.monotonic() + 30
    while True:
        status = client.get(f"/api/participants-convert-status/{job_id}").get_json()
        if status["done"] or time.monotonic() > deadline:
            return (200 if status.get("success") else 400), status


def test_preview_offers_the_sessions_of_a_longitudinal_file(client):
    response = client.post(
        "/api/participants-preview",
        data=_upload(LONGITUDINAL_CSV),
        content_type="multipart/form-data",
    )

    assert response.get_json()["session_candidates"] == [
        {"column": "session", "values": ["baseline", "followup"]}
    ]


def test_preview_of_a_cross_sectional_file_offers_no_sessions(client):
    response = client.post(
        "/api/participants-preview",
        data=_upload(CROSS_SECTIONAL_CSV),
        content_type="multipart/form-data",
    )

    assert response.get_json()["session_candidates"] == []


def test_preview_with_a_chosen_session_shows_only_that_sessions_rows(client):
    response = client.post(
        "/api/participants-preview",
        data=_upload(LONGITUDINAL_CSV, session_column="session", session_value="followup"),
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert payload["participant_count"] == 2
    assert [str(row["age"]) for row in payload["preview_rows"]] == ["31", "41"]


def test_convert_without_a_session_choice_stops_on_the_conflict(client):
    code, status = _convert(client)

    assert code == 400
    assert "one row per participant" in status["error"]
    assert not (client.project / "participants.tsv").exists()


def test_convert_with_a_chosen_session_writes_one_row_per_participant(client):
    code, _status = _convert(client, session_column="session", session_value="baseline")

    assert code == 200
    lines = (client.project / "participants.tsv").read_text().splitlines()
    assert [line.split("\t")[0] for line in lines[1:]] == ["sub-1", "sub-2"]
    assert [line.split("\t")[1] for line in lines[1:]] == ["30", "40"]
