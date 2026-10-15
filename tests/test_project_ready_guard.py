import json

import pytest
from flask import Flask, jsonify

from src.web.project_ready_guard import install_project_ready_guard, is_gate_exempt


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = "t"
    install_project_ready_guard(app)

    @app.route("/api/tool", methods=["POST"])
    def tool():
        return jsonify(ok=True)

    @app.route("/api/projects/save", methods=["POST"])
    def save():
        return jsonify(ok=True)

    @app.route("/converter")
    def page():
        return "page"

    return app.test_client(), tmp_path


def _set_project(client, path):
    with client.session_transaction() as s:
        s["current_project_path"] = str(path)


def test_tool_blocked_with_409(client):
    c, root = client
    (root / "project.json").write_text(json.dumps({}), encoding="utf-8")
    _set_project(c, root)
    r = c.post("/api/tool")
    assert r.status_code == 409
    body = r.get_json()
    assert body["code"] == "project_not_ready" and "Timepoints" in body["missing"]


def test_projects_api_and_pages_stay_open(client):
    c, root = client
    (root / "project.json").write_text(json.dumps({}), encoding="utf-8")
    _set_project(c, root)
    assert c.post("/api/projects/save").status_code == 200
    assert c.get("/converter").status_code == 200


def test_no_project_selected_not_gated(client):
    c, _ = client
    assert c.post("/api/tool").status_code == 200


def test_no_project_json_not_gated(client):
    c, root = client
    _set_project(c, root)
    assert c.post("/api/tool").status_code == 200


def test_fixing_project_unblocks_without_restart(client):
    c, root = client
    pj = root / "project.json"
    pj.write_text("{}", encoding="utf-8")
    _set_project(c, root)
    assert c.post("/api/tool").status_code == 409
    pj.write_text(
        json.dumps(
            {
                "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
                "StudyDesign": {"Timepoints": "single"},
            }
        ),
        encoding="utf-8",
    )
    assert c.post("/api/tool").status_code == 200


def test_exempt_list():
    assert is_gate_exempt("/api/session-map", "POST")
    assert not is_gate_exempt("/api/participants-convert-start", "POST")
