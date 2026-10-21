"""GUI endpoint: the screening-only ids from the table only pass through to the backend."""

import io
import json

import pytest
from flask import Flask

from src.web.blueprints import conversion_participants_blueprint as participants_module

CSV = "token,age\na,30\nb,40\n"


@pytest.fixture
def client(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text('{"StudyDesign": {"Timepoints": "single"}}', encoding="utf-8")
    (project / "participants.tsv").write_text("participant_id\tage\nsub-a\t30\n", encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(participants_module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["current_project_path"] = str(project)
    client.project = project
    return client


def _post(client, **fields):
    return client.post(
        "/api/participants-merge",
        data={"mode": "file", "file": (io.BytesIO(CSV.encode()), "data.csv"), "id_column": "token", **fields},
        content_type="multipart/form-data",
    )


def test_the_ticked_ids_end_up_in_the_group(client):
    response = _post(client, screening_only_ids=json.dumps(["sub-b"]), apply="true")
    assert response.status_code == 200, response.get_json()
    assert "sub-b\t40\tscreening-only" in (client.project / "participants.tsv").read_text()


def test_the_preview_lists_the_source_participants_for_the_table(client):
    rows = _post(client).get_json()["screening_candidates"]
    assert [r["participant_id"] for r in rows] == ["sub-a", "sub-b"]
