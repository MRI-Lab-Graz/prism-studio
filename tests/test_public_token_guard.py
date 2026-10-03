"""`--public` shares the UI on the network with no login, and the app can read,
write and delete files and run rsync/DataLad. A per-launch token must gate every
request in that mode; without the token configured (the default, localhost-only
mode) nothing changes."""

import pytest
from flask import Flask

from src.web.request_guard import install_public_token_guard

TOKEN = "s3cret-token"


def _client(token):
    app = Flask(__name__)
    app.config["PRISM_ACCESS_TOKEN"] = token
    install_public_token_guard(app)

    @app.route("/projects")
    def page():
        return "page"

    @app.route("/health")
    def health():
        return "ok"

    return app.test_client()


def test_no_token_configured_means_open_as_before():
    assert _client(None).get("/projects").status_code == 200


def test_request_without_token_is_rejected():
    assert _client(TOKEN).get("/projects").status_code == 401


def test_wrong_token_is_rejected():
    c = _client(TOKEN)
    assert c.get("/projects?token=nope").status_code == 401
    c.set_cookie("prism_token", "nope")
    assert c.get("/projects").status_code == 401


def test_query_token_is_accepted_and_remembered_in_a_cookie():
    c = _client(TOKEN)
    r = c.get(f"/projects?token={TOKEN}")
    assert r.status_code == 200
    set_cookie = r.headers["Set-Cookie"]
    assert "prism_token=" in set_cookie and "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie
    assert c.get("/projects").status_code == 200  # cookie jar now carries it


def test_header_token_is_accepted_for_scripts():
    assert _client(TOKEN).get("/projects", headers={"X-Prism-Token": TOKEN}).status_code == 200


def test_health_stays_open_for_the_second_launch_check():
    assert _client(TOKEN).get("/health").status_code == 200
