import os
import sys
from pathlib import Path

import pytest
from flask import Blueprint, Flask

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.web.blueprints.projects_datalad_server_blueprint as srv
import src.web.blueprints.validation as val
from src.web import utils as web_utils
from src.web.utils import endpoint_exists


@pytest.fixture
def client():
    app = Flask(
        __name__, root_path=str(APP_ROOT), template_folder="templates", static_folder="static"
    )
    app.secret_key = os.urandom(32)

    @app.context_processor
    def _ctx():
        return {
            "endpoint_exists": endpoint_exists,
            "get_filename_from_path": web_utils.get_filename_from_path,
            "shorten_path": web_utils.shorten_path,
            "get_error_description": web_utils.get_error_description,
            "get_error_documentation_url": web_utils.get_error_documentation_url,
            "current_project": {"path": None, "name": None, "icon": None},
            "prism_static_asset_token": "t",
            "prism_studio_version": "test",
            "latest_prism_studio_version": "test",
            "latest_prism_studio_release_url": "https://example.invalid",
            "prism_studio_update_available": False,
        }

    app.add_url_rule("/", "index", lambda: "")
    app.add_url_rule("/specifications", "specifications", lambda: "")
    projects_stub = Blueprint("projects", __name__)
    projects_stub.add_url_rule("/projects", "projects_page", lambda: "")
    app.register_blueprint(projects_stub)
    for bp_name, rule, ep in [("tools_template_editor", "/template-editor", "template_editor"), ("json_editor", "/editor", "editor_index")]:
        stub = Blueprint(bp_name, bp_name)
        stub.add_url_rule(rule, ep, lambda: "")
        app.register_blueprint(stub)
    app.register_blueprint(val.validation_bp)
    app.register_blueprint(srv.projects_datalad_server_bp)
    with app.test_client() as c:
        yield c


def build(monkeypatch, *, errors, run_prism=True, publishable_dataset=True):
    monkeypatch.setattr(val, "can_publish", lambda p: publishable_dataset)
    monkeypatch.setattr(
        val,
        "format_validation_results",
        lambda issues, stats, root: {
            "summary": {"total_errors": errors, "bids_errors": 0},
            "errors": [],
            "warnings": [],
            # the mode filter recomputes totals from the groups
            "error_groups": {"PRISM1": {"count": errors}} if errors else {},
            "warning_groups": {},
        },
    )
    return val._build_validation_results_payload(
        issues=[], dataset_stats=None, dataset_path="/p", schema_version="stable",
        job_id="j", library_path=None, run_bids=not run_prism, run_prism=run_prism,
        show_bids_warnings=False,
    )


def test_publishable_only_for_clean_prism_run_on_a_publishable_dataset(monkeypatch):
    assert build(monkeypatch, errors=0)["publishable"] is True
    assert build(monkeypatch, errors=2)["publishable"] is False
    assert build(monkeypatch, errors=0, run_prism=False)["publishable"] is False
    assert build(monkeypatch, errors=0, publishable_dataset=False)["publishable"] is False


def test_publish_route_refused_returns_errors_409(client, monkeypatch):
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: Path("/p"))
    monkeypatch.setattr(
        srv, "publish_to_server",
        lambda *a, **k: {"success": False, "reason": "validation_errors", "errors": ["PRISM1"], "message": "m"},
    )
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/p", "name": "A", "email": "a@b.c"})
    assert resp.status_code == 409 and resp.get_json()["errors"] == ["PRISM1"]


def test_publish_route_ignores_any_client_valid_flag(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: Path("/p"))

    def fake(root, **kw):
        seen.update(kw)
        return {"success": True, "reason": "pushed", "errors": [], "message": "ok"}

    monkeypatch.setattr(srv, "publish_to_server", fake)
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/p", "valid": True})
    assert resp.status_code == 200 and "valid" not in seen


def test_publish_route_bad_email_is_400(client, monkeypatch):
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: Path("/p"))
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/p", "name": "A", "email": "nope"})
    assert resp.status_code == 400


def test_publish_route_invalid_project_path_is_400(client):
    resp = client.post("/api/projects/datalad-server/publish", json={"project_path": "/definitely/not/a/project"})
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def _store(results):
    with val._validation_results_lock:
        val._validation_results.clear()
        val._validation_results["rid"] = {
            "results": {**val.format_validation_results([], None, "/p"), "run_prism": True, "run_bids": False, **results},
            "dataset_path": "/p", "temp_dir": None, "filename": "dataset", "created_at": 0,
        }


def test_results_page_shows_publish_button_when_publishable(client):
    _store({"publishable": True})
    html = client.get("/results/rid").get_data(as_text=True)
    assert 'id="publishBtn"' in html and 'data-project-path="/p"' in html


def test_results_page_disables_publish_when_errors(client):
    _store({"publishable": False, "publish_capable": True})
    val._validation_results["rid"]["results"]["summary"]["total_errors"] = 3
    html = client.get("/results/rid").get_data(as_text=True)
    assert 'id="publishBtn"' not in html
    assert "Fix 3 error(s) before publishing" in html


def test_publish_route_uncommitted_changes_is_400(client, monkeypatch):
    monkeypatch.setattr(srv, "_resolve_project_root_path", lambda p: Path("/p"))
    monkeypatch.setattr(
        srv, "publish_to_server",
        lambda *a, **k: {"success": False, "reason": "uncommitted_changes", "errors": ["M f"], "message": "m"},
    )
    assert client.post("/api/projects/datalad-server/publish", json={"project_path": "/p"}).status_code == 400


@pytest.mark.parametrize("body", [[1], "x", 3])
def test_publish_route_non_object_body_is_400(client, body):
    assert client.post("/api/projects/datalad-server/publish", json=body).status_code == 400


def test_payload_exposes_publish_capable_separately(monkeypatch):
    assert build(monkeypatch, errors=2)["publish_capable"] is True
    assert build(monkeypatch, errors=2, publishable_dataset=False)["publish_capable"] is False


def test_disabled_button_only_for_capable_datasets(client):
    _store({"publishable": False, "publish_capable": False})
    val._validation_results["rid"]["results"]["summary"]["total_errors"] = 3
    assert "before publishing" not in client.get("/results/rid").get_data(as_text=True)
    val._validation_results["rid"]["results"]["publish_capable"] = True
    assert "Fix 3 error(s) before publishing" in client.get("/results/rid").get_data(as_text=True)


def test_results_page_does_not_reload_after_validation_errors(client):
    _store({"publishable": True})
    assert "location.reload" not in client.get("/results/rid").get_data(as_text=True)
