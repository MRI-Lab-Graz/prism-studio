import json
import sys
from pathlib import Path

import pytest
from flask import Flask

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.session_map_blueprint import session_map_bp  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(session_map_bp)
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))
    return app.test_client(), root


def test_get_returns_declaration_and_map(client):
    http, root = client
    body = http.get("/api/session-map", query_string={"project_path": str(root)}).get_json()
    assert body == {"ok": True, "timepoints": "multiple", "map": {}}


def test_post_adds_entries_and_keeps_existing_ones(client):
    http, root = client
    http.post("/api/session-map", json={"project_path": str(root), "entries": {"pre": "1"}})
    resp = http.post("/api/session-map", json={"project_path": str(root), "entries": {"post": "2"}})
    assert resp.get_json() == {"ok": True, "map": {"pre": "1", "post": "2"}}


def test_post_rejects_an_invalid_target_and_writes_nothing(client):
    http, root = client
    resp = http.post("/api/session-map", json={"project_path": str(root), "entries": {"pre": "ses-1"}})
    assert resp.status_code == 400 and "letters and digits" in resp.get_json()["error"]
    assert not (root / "code" / "session_map.json").exists()


def test_post_without_entries_is_a_400(client):
    http, root = client
    assert http.post("/api/session-map", json={"project_path": str(root)}).status_code == 400
