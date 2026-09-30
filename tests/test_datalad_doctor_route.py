"""GET /api/projects/datalad/doctor is a thin adapter over src.datalad_doctor.run_doctor."""

import importlib
import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def test_doctor_handler_returns_checks_for_the_given_url(monkeypatch):
    mod = importlib.import_module("src.web.blueprints.projects_lifecycle_handlers")
    seen = {}

    def fake(url):
        seen["url"] = url
        return [{"name": "git", "ok": True, "detail": "", "fix": ""}]

    monkeypatch.setattr(mod, "run_doctor", fake)
    with Flask(__name__).test_request_context("/?url=ria%2Bssh://u@h/s"):
        body = mod.handle_datalad_doctor().get_json()
    assert seen["url"] == "ria+ssh://u@h/s"
    assert body == {"success": True, "checks": [{"name": "git", "ok": True, "detail": "", "fix": ""}]}
