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


@pytest.mark.parametrize("path", ["/api/config", "/api/filesystem-context"])
def test_read_only_projects_page_gets_exempt(path):
    assert is_gate_exempt(path, "GET")


def test_guard_installed_after_project_selection_hook():
    from pathlib import Path

    src = (Path(__file__).parents[1] / "app" / "prism-studio.py").read_text(encoding="utf-8")
    assert src.index("def ensure_project_selected_first") < src.index("install_project_ready_guard(app)")


# ---- review round: the GUI exemption list follows the CLI gate and the spec ----

@pytest.mark.parametrize("path", [
    "/api/projects/anc-export", "/api/projects/openminds-export", "/api/projects/template-export",
    "/api/projects/export", "/api/projects/export/start", "/api/projects/export/deface",
    "/api/projects/export/git-lfs", "/api/projects/datalad-server/publish",
    "/api/projects/datalad-server/sync/start", "/api/projects/datalad-server/finalize/start",
    "/api/projects/datalad/remove-scans-tsv", "/api/projects/participants",
])
def test_routes_that_export_publish_or_write_project_data_are_gated_like_their_cli_twins(path):
    assert not is_gate_exempt(path, "POST")


@pytest.mark.parametrize("path,method", [
    ("/api/projects/create", "POST"), ("/api/projects/current", "POST"),
    ("/api/projects/study-metadata", "POST"), ("/api/projects/description", "POST"),
    ("/api/projects/export/structure", "POST"),         # the metadata form's missing-files rows use it
    ("/api/projects/export/abc123/status", "GET"),      # a running job can still be read and cancelled
    ("/api/projects/export/abc123/cancel", "DELETE"),
    ("/api/projects/datalad/doctor", "GET"),            # a diagnostic
    ("/api/projects/datalad/save", "POST"),             # saving an unfinished project stays possible
    ("/api/projects/participants", "GET"),
])
def test_routes_that_open_create_inspect_or_fix_the_project_stay_open(path, method):
    assert is_gate_exempt(path, method)


@pytest.mark.parametrize("path", [
    "/api/environment-convert-start", "/api/environment-preview", "/api/environment-scan-mri",
])
def test_environment_routes_are_exempt_like_the_cli_environment_command(path):
    assert is_gate_exempt(path, "POST")


@pytest.mark.parametrize("path", [
    "/api/generate-lss", "/api/generate-boilerplate", "/api/generate-pavlovia",
    "/api/list-library-files-merged",
])
def test_survey_generator_routes_do_not_work_on_the_project_and_stay_open(path):
    assert is_gate_exempt(path, "POST")


def test_the_409_body_says_success_false_like_the_other_error_responses(client):
    c, root = client
    (root / "project.json").write_text(json.dumps({}), encoding="utf-8")
    _set_project(c, root)
    assert c.post("/api/tool").get_json()["success"] is False
