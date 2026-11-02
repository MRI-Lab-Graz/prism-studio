"""Studio's session-order endpoints are adapters over src.session_order, same files as the CLI."""

import io
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.session_order import ORDER_FILE  # noqa: E402
from src.web.blueprints.session_assignments_blueprint import session_assignments_bp  # noqa: E402
from src.web.blueprints.session_order_blueprint import session_order_bp  # noqa: E402

PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "multiple", "SessionLabels": "content"},
}


def make_project(path):
    path.mkdir()
    (path / "project.json").write_text(json.dumps(PROJECT))
    return path


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(session_order_bp)
    app.register_blueprint(session_assignments_bp)
    project = make_project(tmp_path / "proj")
    http = app.test_client()
    with http.session_transaction() as s:
        s["current_project_path"] = str(project)
    http.project = project
    return http


def prepared_file(tmp_path):
    path = tmp_path / "order.csv"
    pd.DataFrame(
        {"participant_id": ["P01", "P01", "P02"], "session_number": [1, 2, 1], "session": ["a", "b", "b"]}
    ).to_csv(path, index=False)
    return path


def test_get_returns_the_declaration_and_the_order(client):
    client.post("/api/session-order", json={"participant": "P01", "number": "1", "session": "sleepdep"})

    assert client.get("/api/session-order").get_json() == {
        "ok": True, "session_labels": "content", "order": {"P01": {"1": "sleepdep"}},
    }


def test_post_sets_and_clears(client):
    client.post("/api/session-order", json={"participant": "P01", "number": "1", "session": "a"})
    client.post("/api/session-order", json={"participant": "P01", "number": "2", "session": "b"})

    cleared = client.post("/api/session-order", json={"participant": "P01", "number": "1", "clear": True})

    assert cleared.get_json() == {"ok": True, "order": {"P01": {"2": "b"}}}


def test_post_rejects_an_invalid_name_and_writes_nothing(client):
    resp = client.post("/api/session-order", json={"participant": "P01", "number": "1", "session": "sleep dep"})

    assert resp.status_code == 400 and "letters and digits" in resp.get_json()["error"]
    assert not (client.project / ORDER_FILE).exists()


def test_import_uploads_a_prepared_file(client, tmp_path):
    prepared = prepared_file(tmp_path)

    resp = client.post(
        "/api/session-order/import",
        data={"file": (io.BytesIO(prepared.read_bytes()), "order.csv")},
        content_type="multipart/form-data",
    )

    assert resp.get_json()["order"] == {"P01": {"1": "a", "2": "b"}, "P02": {"1": "b"}}


def test_review_tells_the_page_the_declaration_and_the_order(client, tmp_path):
    client.post("/api/session-order", json={"participant": "P01", "number": "1", "session": "sleepdep"})
    source = tmp_path / "in.csv"
    pd.DataFrame(
        [{"id": "1", "token": "P01", "startdate": "2026-01-05 10:00:00", "submitdate": "x"}]
    ).to_csv(source, index=False)

    body = client.post(
        "/api/session-assignments/review",
        data={"file": (io.BytesIO(source.read_bytes()), "in.csv"), "id_column": "token"},
        content_type="multipart/form-data",
    ).get_json()

    assert body["session_labels"] == "content"
    assert body["order"] == {"P01": {"1": "sleepdep"}}
    assert (body["rows"][0]["number"], body["rows"][0]["session"]) == ("1", "sleepdep")
