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
    ("get", "/api/spec/local"), ("post", "/api/spec/local/add-term"),
    ("post", "/api/spec/local/remove"), ("post", "/api/spec/propose"),
])
def test_every_route_needs_an_open_project(client, method, url):
    response = getattr(client, method)(url, json={})
    assert response.status_code == 400 and response.get_json() == {"success": False, "error": "Open a project first"}


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
