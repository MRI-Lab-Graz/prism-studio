"""Any web page the user visits can fire requests at http://127.0.0.1:<port>.

The Host-header check does not stop that (the Host really is 127.0.0.1), so
state-changing / API requests that a browser marks as cross-site (or whose
Origin is not this server) must be rejected.
"""

from __future__ import annotations

import pytest
from flask import Flask

from src.web.request_guard import install_cross_site_guard


@pytest.fixture
def client():
    app = Flask(__name__)
    install_cross_site_guard(app)

    @app.route("/shutdown", methods=["POST"])
    def shutdown():
        return "bye"

    @app.route("/api/projects/datalad/doctor")
    def doctor():
        return "ok"

    @app.route("/projects")
    def page():
        return "page"

    return app.test_client()


def h(site=None, mode=None, origin=None):
    out = {}
    if site:
        out["Sec-Fetch-Site"] = site
    if mode:
        out["Sec-Fetch-Mode"] = mode
    if origin:
        out["Origin"] = origin
    return out


def test_cross_site_post_blocked(client):
    r = client.post("/shutdown", headers=h("cross-site", "navigate"))
    assert r.status_code == 403


def test_cross_site_img_get_to_api_blocked(client):
    assert client.get("/api/projects/datalad/doctor", headers=h("cross-site", "no-cors")).status_code == 403


def test_cross_site_navigation_to_api_blocked(client):
    assert client.get("/api/projects/datalad/doctor", headers=h("cross-site", "navigate")).status_code == 403


def test_foreign_origin_blocked_without_fetch_metadata(client):
    assert client.post("/shutdown", headers=h(origin="http://evil.example")).status_code == 403
    assert client.post("/shutdown", headers=h(origin="null")).status_code == 403


def test_same_site_other_port_blocked(client):
    assert client.post("/shutdown", headers=h("same-site", "cors")).status_code == 403


def test_same_origin_allowed(client):
    assert client.post("/shutdown", headers=h("same-origin", "cors", "http://localhost")).status_code == 200
    assert client.get("/api/projects/datalad/doctor", headers=h("same-origin", "cors")).status_code == 200


def test_no_metadata_cli_clients_allowed(client):
    assert client.post("/shutdown").status_code == 200


def test_user_typed_url_and_cross_site_link_to_page_allowed(client):
    assert client.get("/projects", headers=h("none", "navigate")).status_code == 200
    assert client.get("/projects", headers=h("cross-site", "navigate")).status_code == 200
