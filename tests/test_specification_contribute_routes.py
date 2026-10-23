"""The Contribute page and its routes (phase 1, Task 6): thin adapters over src.spec_overlay."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from flask import Flask

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "app"), str(REPO)]

from src.web.blueprints.specification_contribute import specification_contribute_bp  # noqa: E402
from src.web.project_ready_guard import is_gate_exempt  # noqa: E402

FORM = "https://github.com/MRI-Lab-Graz/prism-specification/issues/new"


def _project(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "dataset_description.json").write_text("{}", encoding="utf-8")
    (root / "biosample-saliva_biosample.json").write_text(json.dumps({
        "Technical": {"SpecimenType": "saliva"}, "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-23"},
        "sample_id": {"Description": "Tube", "Units": "n/a"},
        "dhea_s": {"Description": "Salivary DHEA-S", "Units": "pg/mL", "MinValue": 0}}), encoding="utf-8")
    folder = root / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (folder / "sub-01_ses-1_biosample-saliva_biosample.tsv").write_text("sample_id\tdhea_s\nS-1\t5\n", encoding="utf-8")
    return root


def _tsv(project: Path) -> str:
    return str(project / "sub-01" / "ses-1" / "biosample" / "sub-01_ses-1_biosample-saliva_biosample.tsv")


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test-secret"  # pragma: allowlist secret
    app.register_blueprint(specification_contribute_bp)
    return app.test_client()


def _open(client, project: Path):
    with client.session_transaction() as session:
        session["current_project_path"] = str(project)


@pytest.mark.parametrize("method,url", [
    ("post", "/api/spec/local/add-term"), ("post", "/api/spec/local/remove"), ("post", "/api/spec/propose"),
    ("post", "/api/spec/local/add-values"), ("post", "/api/spec/local/remove-values"),
])
def test_every_write_route_needs_an_open_project(client, method, url):
    response = getattr(client, method)(url, json={})
    assert response.status_code == 400 and response.get_json() == {"success": False, "error": "Open a project first"}


def test_the_listing_without_a_project_is_a_message_not_an_error(client):
    """The page can be opened without a project; a 4xx would put an error in the browser console on every visit."""
    response = client.get("/api/spec/local")
    assert response.status_code == 200 and response.get_json() == {"success": False, "error": "Open a project first"}


def test_list_shows_unknown_metrics_and_local_items(client, tmp_path):
    project = _project(tmp_path / "p")
    _open(client, project)
    data = client.get("/api/spec/local").get_json()
    assert data["success"] and data["items"] == [] and [m["column"] for m in data["unknown_metrics"]] == ["dhea_s"]


def test_add_term_then_list_then_propose_then_remove(client, tmp_path):
    project = _project(tmp_path / "p")
    _open(client, project)
    added = client.post("/api/spec/local/add-term", json={"data_file": _tsv(project), "column": "dhea_s", "label": "DHEA-S"})
    assert added.status_code == 200 and added.get_json()["success"]
    listing = client.get("/api/spec/local").get_json()
    assert [(i["id"], i["status"]) for i in listing["items"]] == [("prism:dhea-s", "local"), ("prism:dhea-s.saliva", "local")]
    assert listing["unknown_metrics"] == []
    proposed = client.post("/api/spec/propose", json={"id": "prism:dhea-s"}).get_json()
    assert proposed["success"] and proposed["problems"] == [] and proposed["issue_url"].startswith(FORM)
    assert len(proposed["proposal"]["terms"]) == 2
    removed = client.post("/api/spec/local/remove", json={"id": "prism:dhea-s"}).get_json()
    assert removed["success"] and len(removed["removed"]) == 2
    assert client.get("/api/spec/local").get_json()["items"] == []


def test_add_term_refuses_an_official_metric_with_a_message(client, tmp_path):
    project = _project(tmp_path / "p")
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["cort"] = {"Description": "d", "Units": "nmol/L"}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _open(client, project)
    response = client.post("/api/spec/local/add-term", json={"data_file": _tsv(project), "column": "cort"})
    assert response.status_code == 400 and "prism:cortisol" in response.get_json()["error"]


def test_add_term_needs_a_column_and_a_data_file_inside_the_project(client, tmp_path):
    project = _project(tmp_path / "p")
    outside = _project(tmp_path / "other")
    _open(client, project)
    assert client.post("/api/spec/local/add-term", json={"data_file": _tsv(project)}).status_code == 400
    assert client.post("/api/spec/local/add-term", json={"column": "dhea_s"}).status_code == 400
    escape = client.post("/api/spec/local/add-term", json={"data_file": _tsv(outside), "column": "dhea_s"})
    assert escape.status_code == 400 and "inside the project" in escape.get_json()["error"]
    assert not (project / "code").exists() and not (outside / "code").exists()


def test_remove_and_propose_reject_unknown_ids(client, tmp_path):
    _open(client, _project(tmp_path / "p"))
    assert client.post("/api/spec/local/remove", json={"id": "prism:nope"}).status_code == 400
    assert client.post("/api/spec/propose", json={"id": "prism:../x"}).status_code == 400
    assert client.post("/api/spec/propose", json={}).status_code == 400


def test_the_routes_are_exempt_from_the_project_ready_gate():
    assert is_gate_exempt("/api/spec/local", "GET") and is_gate_exempt("/api/spec/propose", "POST")


def test_the_script_never_writes_project_data_as_html():
    source = (REPO / "app" / "static" / "js" / "modules" / "specification" / "contribute.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert forbidden not in source, forbidden


_RENDER = f"""
import importlib.util, sys
sys.path[:0] = [{str(REPO / "app")!r}, {str(REPO)!r}]
spec = importlib.util.spec_from_file_location("ps", {str(REPO / "app" / "prism-studio.py")!r})
m = importlib.util.module_from_spec(spec); sys.modules["ps"] = m; spec.loader.exec_module(m)
c = m.app.test_client()
for name, path in (("contribute", "/specifications/contribute"), ("survey", "/specifications/survey"), ("bogus", "/specifications/bogus")):
    r = c.get(path)
    open(sys.argv[1] + "/" + name + ".status", "w").write(str(r.status_code))
    open(sys.argv[1] + "/" + name + ".html", "wb").write(r.data)
"""


def test_the_page_renders_and_every_specification_page_links_it(tmp_path):
    subprocess.run([sys.executable, "-c", _RENDER, str(tmp_path)], check=True, cwd=REPO,
                   env={**__import__("os").environ, "PRISM_SKIP_VENV_CHECK": "1"}, capture_output=True)
    contribute = (tmp_path / "contribute.html").read_text(encoding="utf-8")
    assert (tmp_path / "contribute.status").read_text() == "200" and (tmp_path / "bogus.status").read_text() == "404"
    assert "New metric" in contribute and 'id="spec-contribute"' in contribute and "contribute.js" in contribute
    assert "/specifications/contribute" in (tmp_path / "survey.html").read_text(encoding="utf-8")


# --- proposal format v2: several terms ------------------------------------------------------------

def _two_local(client, tmp_path):
    project = _project(tmp_path / "p")
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["ferr_ugl"] = {"Description": "Ferritin", "Units": "ug/L", "MinValue": 0}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _open(client, project)
    for column, label in (("dhea_s", "DHEA-S"), ("ferr_ugl", "Ferritin")):
        assert client.post("/api/spec/local/add-term", json={"data_file": _tsv(project), "column": column, "label": label}).get_json()["success"]
    return project


def test_propose_all_returns_one_v2_document(client, tmp_path):
    _two_local(client, tmp_path)
    data = client.post("/api/spec/propose", json={"all": True}).get_json()
    assert data["success"] and data["problems"] == [] and data["skipped"] == []
    assert data["document"]["format"] == "prism-proposal/2" and len(data["document"]["files"]) == 4
    assert len(data["proposal"]["terms"]) == 4


def test_propose_accepts_a_list_of_ids(client, tmp_path):
    _two_local(client, tmp_path)
    data = client.post("/api/spec/propose", json={"ids": ["prism:dhea-s", "prism:ferritin"]}).get_json()
    assert data["success"] and len(data["document"]["files"]) == 4
    one = client.post("/api/spec/propose", json={"id": "prism:dhea-s"}).get_json()
    assert one["success"] and len(one["document"]["files"]) == 2


@pytest.mark.parametrize("body", [
    {}, {"ids": []}, {"ids": "prism:dhea-s"}, {"ids": [1]}, {"ids": ["prism:../x"]}, {"all": "yes"}, {"id": 5}, {"all": False},
])
def test_propose_rejects_bad_bodies(client, tmp_path, body):
    _two_local(client, tmp_path)
    response = client.post("/api/spec/propose", json=body)
    assert response.status_code == 400 and response.get_json()["success"] is False


def test_the_page_script_shows_and_downloads_the_document_that_is_sent():
    source = (REPO / "app" / "static" / "js" / "modules" / "specification" / "contribute.js").read_text(encoding="utf-8")
    assert "data.document" in source and "Share all" in (REPO / "app" / "templates" / "specifications_contribute.html").read_text(encoding="utf-8")


_NO_PROJECT = f"""
import importlib.util, sys
sys.path[:0] = [{str(REPO / "app")!r}, {str(REPO)!r}]
spec = importlib.util.spec_from_file_location("ps", {str(REPO / "app" / "prism-studio.py")!r})
m = importlib.util.module_from_spec(spec); sys.modules["ps"] = m; spec.loader.exec_module(m)
c = m.app.test_client()  # a fresh session: no project is open
out = []
for method, url in (("get", "/api/spec/local"), ("post", "/api/spec/local/add-term"), ("post", "/api/spec/local/remove"), ("post", "/api/spec/propose")):
    r = getattr(c, method)(url, json={{}})
    out.append((method, url, r.status_code, r.content_type.split(";")[0], r.get_json(silent=True)))
import json
open(sys.argv[1], "w").write(json.dumps(out))  # the app swallows stdout
"""


def test_without_an_open_project_the_real_app_answers_json_not_a_redirect(tmp_path):
    """Regression: the app's project guard redirected GET /api/spec/local to the project picker (an HTML page)."""
    result_file = tmp_path / "result.json"
    subprocess.run([sys.executable, "-c", _NO_PROJECT, str(result_file)], cwd=REPO, check=True, capture_output=True,
                   env={**__import__("os").environ, "PRISM_SKIP_VENV_CHECK": "1"})
    for method, url, status, content_type, body in json.loads(result_file.read_text()):
        assert (status, content_type) == (200 if method == "get" else 400, "application/json"), (method, url, status, content_type)
        assert body == {"success": False, "error": "Open a project first"}, (url, body)


def test_propose_shares_the_patch(client, tmp_path):
    from src.spec_overlay import add_local_values

    project = _project(tmp_path / "p")
    _open(client, project)
    add_local_values(project, "Technical.SpecimenType", ["sweat"])
    alone = client.post("/api/spec/propose", json={"patch": True}).get_json()
    assert alone["success"] and list(alone["document"]["files"]) == ["patches/biosample.json"] and alone["problems"] == []
    everything = client.post("/api/spec/propose", json={"all": True}).get_json()
    assert everything["success"] and "patches/biosample.json" in everything["document"]["files"]


def test_propose_patch_without_additions_is_a_400(client, tmp_path):
    _open(client, _project(tmp_path / "p"))
    response = client.post("/api/spec/propose", json={"patch": True})
    assert response.status_code == 400 and response.get_json()["success"] is False


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_propose_rejects_a_non_boolean_patch(client, tmp_path, value):
    _two_local(client, tmp_path)
    assert client.post("/api/spec/propose", json={"id": "prism:dhea-s", "patch": value}).status_code == 400


def _sweat(project: Path) -> None:
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["Technical"]["SpecimenType"] = "sweat"
    sidecar.write_text(json.dumps(data), encoding="utf-8")


def test_list_shows_unknown_values_and_the_extendable_fields(client, tmp_path):
    project = _project(tmp_path / "p")
    _sweat(project)
    _open(client, project)
    data = client.get("/api/spec/local").get_json()
    assert [(v["field"], v["value"]) for v in data["unknown_values"]] == [("Technical.SpecimenType", "sweat")]
    assert "Technical.SpecimenType" in data["fields"]


def test_add_values_list_remove_values_round_trip(client, tmp_path):
    project = _project(tmp_path / "p")
    _sweat(project)
    _open(client, project)
    body = {"field": "Technical.SpecimenType", "values": ["sweat"]}
    added = client.post("/api/spec/local/add-values", json=body).get_json()
    assert added["success"] and added["skipped"] == []
    data = client.get("/api/spec/local").get_json()
    assert data["unknown_values"] == []
    assert [(i["layer"], i["field"], i["value"], i["status"]) for i in data["items"]] == [(2, "Technical.SpecimenType", "sweat", "local")]
    assert client.post("/api/spec/local/remove-values", json=body).get_json()["success"]
    assert client.get("/api/spec/local").get_json()["items"] == []


@pytest.mark.parametrize("body", [
    {}, {"field": "Technical.SpecimenType"}, {"values": ["sweat"]}, {"field": 5, "values": ["sweat"]},
    {"field": "Technical.SpecimenType", "values": "sweat"}, {"field": "Technical.SpecimenType", "values": [1]},
    {"field": "Technical.SpecimenType", "values": []}, {"field": "../../etc", "values": ["x"]},
    {"field": "Technical.Nope", "values": ["x"]}, {"field": "Technical.SpecimenType", "values": ["Bad Value"]},
])
def test_add_values_rejects_bad_bodies_and_writes_nothing(client, tmp_path, body):
    project = _project(tmp_path / "p")
    _open(client, project)
    response = client.post("/api/spec/local/add-values", json=body)
    assert response.status_code == 400 and response.get_json()["success"] is False
    assert not (project / "code").exists()


def test_remove_values_rejects_what_is_not_there(client, tmp_path):
    _open(client, _project(tmp_path / "p"))
    response = client.post("/api/spec/local/remove-values", json={"field": "Technical.SpecimenType", "values": ["sweat"]})
    assert response.status_code == 400 and response.get_json()["success"] is False


# --- the propose page: routes that need no project ---

_METRIC = {"name": "Zzzquux", "description": "A made up measurement", "units": "pg/mL", "specimen": "saliva"}


def test_catalog_without_a_project(client):
    response = client.get("/api/spec/catalog")
    data = response.get_json()
    assert response.status_code == 200 and data["success"] is True and data["project_open"] is False
    assert "biosample" in [m["name"] for m in data["modalities"]]


def test_catalog_with_a_project(client, tmp_path):
    _open(client, _project(tmp_path / "p"))
    assert client.get("/api/spec/catalog").get_json()["project_open"] is True


def test_propose_values_without_a_project(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = client.post("/api/spec/propose-values", json={"field": "Technical.SpecimenType", "values": ["sweat"]}).get_json()
    assert data["success"] is True and data["issue_url"].startswith(FORM)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("body", [
    {"field": "Technical.SpecimenType", "values": "sweat"}, {"values": ["sweat"]}, {"field": 3, "values": ["sweat"]},
    {"field": "Technical.SpecimenType", "values": [1]}, {"modality": 5, "field": "Technical.SpecimenType", "values": ["sweat"]},
])
def test_propose_values_rejects_bad_body(client, body):
    response = client.post("/api/spec/propose-values", json=body)
    assert response.status_code == 400 and response.get_json()["success"] is False


def test_propose_values_already_allowed_is_an_error_message(client):
    response = client.post("/api/spec/propose-values", json={"field": "Technical.SpecimenType", "values": ["saliva"]})
    assert response.status_code == 400 and "already allowed" in response.get_json()["error"]


def test_propose_metric_without_a_project(client):
    data = client.post("/api/spec/propose-metric", json=_METRIC).get_json()
    assert data["success"] is True and data["issue_url"].startswith(FORM)


def test_propose_metric_uses_the_projects_own_specimens(client, tmp_path):
    _open(client, _project(tmp_path / "p"))
    assert client.post("/api/spec/local/add-values", json={"field": "Technical.SpecimenType", "values": ["sweat"]}).get_json()["success"]
    sweat = dict(_METRIC, specimen="sweat")
    assert client.post("/api/spec/propose-metric", json=sweat).get_json()["problems"] == []
    client.post("/api/spec/local/remove-values", json={"field": "Technical.SpecimenType", "values": ["sweat"]})
    assert client.post("/api/spec/propose-metric", json=sweat).get_json()["problems"] != []


def test_propose_metric_official_name_is_an_error(client):
    response = client.post("/api/spec/propose-metric", json=dict(_METRIC, name="Cortisol"))
    assert response.status_code == 400 and "official" in response.get_json()["error"]


@pytest.mark.parametrize("body", [
    {}, dict(_METRIC, name=3), dict(_METRIC, aliases="x"), dict(_METRIC, aliases=[1]), dict(_METRIC, modality=[]),
])
def test_propose_metric_rejects_bad_body(client, body):
    assert client.post("/api/spec/propose-metric", json=body).status_code == 400


def test_new_routes_pass_the_project_gate():
    assert is_gate_exempt("/api/spec/catalog", "GET")
    assert is_gate_exempt("/api/spec/propose-values", "POST") and is_gate_exempt("/api/spec/propose-metric", "POST")


def test_oversized_proposal_reports_problems(client):
    data = client.post("/api/spec/propose-metric", json=dict(_METRIC, description="x" * 200000)).get_json()
    assert data["success"] is True and data["problems"]
