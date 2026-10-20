"""GUI endpoints for the session review table."""

import io

import pytest
from flask import Flask

from src.web.blueprints.session_assignments_blueprint import session_assignments_bp
from src.session_assignments import load_session_assignments
from tests.lsa_fixtures import make_lsa


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(session_assignments_bp)
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text('{"StudyDesign": {"Timepoints": "single"}}')
    http = app.test_client()
    with http.session_transaction() as s:
        s["current_project_path"] = str(project)
    http.project = project
    return http


def _upload(tmp_path):
    return {
        "file": (io.BytesIO(make_lsa(tmp_path).read_bytes()), "repeated.lsa"),
        "id_column": "token",
    }


def test_review_returns_the_rows_and_warnings(client, tmp_path):
    body = client.post(
        "/api/session-assignments/review", data=_upload(tmp_path),
        content_type="multipart/form-data",
    ).get_json()

    by_id = {r["response_id"]: r for r in body["rows"]}
    assert (by_id["2"]["session"], by_id["1"]["reason"]) == ("1", "incomplete")
    assert any("No completed response for: b" in w for w in body["warnings"])


def test_review_applies_the_projects_saved_decisions(client, tmp_path):
    client.post("/api/session-assignments",
                json={"response_id": "4", "session": "pre", "survey_id": "999999"})

    body = client.post(
        "/api/session-assignments/review", data=_upload(tmp_path),
        content_type="multipart/form-data",
    ).get_json()

    assert {r["response_id"]: r for r in body["rows"]}["4"]["session"] == "pre"


def test_post_saves_and_clears_a_decision(client):
    saved = client.post("/api/session-assignments", json={"response_id": "7", "skip": True})
    assert saved.get_json() == {"ok": True, "responses": {"7": {"skip": True}}}
    assert load_session_assignments(client.project) == {"7": {"skip": True}}

    cleared = client.post("/api/session-assignments", json={"response_id": "7", "clear": True})
    assert cleared.get_json() == {"ok": True, "responses": {}}


def test_post_rejects_an_empty_decision(client):
    resp = client.post("/api/session-assignments", json={"response_id": "7"})

    assert resp.status_code == 400
    assert "exactly one" in resp.get_json()["error"].lower()
    assert load_session_assignments(client.project) == {}


def test_review_returns_the_survey_id(client, tmp_path):
    body = client.post(
        "/api/session-assignments/review", data=_upload(tmp_path),
        content_type="multipart/form-data",
    ).get_json()

    assert body["survey_id"] == "999999"


def test_post_scopes_the_decision_to_the_survey(client):
    client.post("/api/session-assignments", json={"response_id": "7", "skip": True, "survey_id": "111"})

    assert load_session_assignments(client.project, "111") == {"7": {"skip": True}}
    assert load_session_assignments(client.project) == {}


def test_post_rejects_a_non_string_session(client):
    resp = client.post("/api/session-assignments", json={"response_id": "7", "session": 5})

    assert resp.status_code == 400
    assert load_session_assignments(client.project) == {}


def test_review_with_an_invalid_project_path_is_a_400(client, tmp_path):
    resp = client.post(
        "/api/session-assignments/review",
        data={**_upload(tmp_path), "project_path": str(tmp_path / "does-not-exist")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_saves_an_include_decision(client):
    resp = client.post("/api/session-assignments",
                       json={"response_id": "1", "include": True, "survey_id": "999999"})

    assert resp.status_code == 200
    assert load_session_assignments(client.project, "999999") == {"1": {"include": True}}


def test_review_hides_responses_already_in_the_project_when_asked(client, tmp_path):
    from src.survey_existing import record_imports, row_fingerprint

    fp = row_fingerprint({"startdate": "2026-03-01 11:00:00", "token": "a"}, ["startdate", "token"])
    record_imports(client.project, client.project, [("sub-a", "ses-1", fp)])

    def review(**extra):
        return client.post(
            "/api/session-assignments/review", data={**_upload(tmp_path), **extra},
            content_type="multipart/form-data",
        ).get_json()

    assert "2" in {r["response_id"] for r in review()["rows"]}
    hidden = review(skip_existing="true")
    assert "2" not in {r["response_id"] for r in hidden["rows"]}
    assert {r["response_id"]: r for r in hidden["rows"]}["3"]["session"] == "2"
