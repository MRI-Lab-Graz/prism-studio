"""`prism-studio -rp NAME`: start with a recent project, matched by name, on the project page."""

import importlib.util
import sys
from pathlib import Path

import pytest
from flask import Flask, session

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "app"), str(REPO)]

from src.recent_projects import find_recent_project, recent_project_notice  # noqa: E402

RECENT = [
    {"name": "Highlands", "path": "/p/highlands"},
    {"name": "high", "path": "/p/high"},
    {"name": "Lowlands", "path": "/p/low"},
]


def test_an_exact_name_wins_over_a_longer_one_that_also_matches():
    assert find_recent_project(RECENT, "high")["path"] == "/p/high"


def test_the_match_ignores_case_and_accepts_part_of_a_name():
    assert find_recent_project(RECENT, "LOWL")["path"] == "/p/low"


def test_the_most_recent_of_several_partial_matches_is_taken():
    assert find_recent_project(RECENT[:1] + RECENT[2:] + [{"name": "Highest", "path": "/p/x"}], "high")["path"] == "/p/highlands"


def test_no_match_and_a_blank_name_find_nothing():
    assert find_recent_project(RECENT, "nope") is None
    assert find_recent_project(RECENT, "  ") is None


def test_the_notice_says_which_project_opens():
    assert recent_project_notice(RECENT, "high") == "Opening recent project 'high' (/p/high)"


def test_the_notice_says_why_nothing_opens_and_what_is_there():
    assert recent_project_notice(RECENT, "nope") == (
        "No recent project matches 'nope' (recent: Highlands, high, Lowlands); starting as usual"
    )
    assert recent_project_notice([], "nope") == "No recent project matches 'nope' (the recent list is empty); starting as usual"


def test_the_flag_is_on_the_parser():
    spec = importlib.util.spec_from_file_location("ps_rp", REPO / "app" / "prism-studio.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module._build_parser()
    assert parser.parse_args(["-rp", "high"]).recent_project == "high"
    assert parser.parse_args([]).recent_project is None


@pytest.fixture
def client(monkeypatch, tmp_path):
    from src.web.blueprints import projects as projects_module

    (tmp_path / "high").mkdir()
    monkeypatch.setattr(
        projects_module, "_load_recent_projects",
        lambda: [{"name": "high", "path": str(tmp_path / "high"), "icon": "x"}],
    )
    monkeypatch.setattr(projects_module, "_save_last_project", lambda *a, **k: None)
    monkeypatch.setattr(projects_module, "activate_project_session", lambda *a, **k: None)
    app = Flask(__name__)
    app.secret_key = "t"
    app.register_blueprint(projects_module.projects_bp)
    return app, app.test_client(), tmp_path


def test_the_open_recent_route_opens_the_project_and_lands_on_the_project_page(client):
    app, c, tmp_path = client
    app.config["PRISM_OPEN_RECENT"] = "high"
    response = c.get("/api/projects/open-recent")
    assert response.status_code == 302 and response.headers["Location"].endswith("/projects")
    with c.session_transaction() as s:
        assert s["current_project_path"] == str(tmp_path / "high")


def test_an_unknown_name_starts_the_standard_page_and_opens_nothing(client):
    app, c, _ = client
    app.config["PRISM_OPEN_RECENT"] = "nope"
    response = c.get("/api/projects/open-recent")
    assert response.headers["Location"].endswith("/")
    with c.session_transaction() as s:
        assert "current_project_path" not in s


def test_the_name_is_used_once_so_a_page_cannot_switch_projects_later(client):
    app, c, _ = client
    app.config["PRISM_OPEN_RECENT"] = "high"
    c.get("/api/projects/open-recent")
    with c.session_transaction() as s:
        s.clear()
    c.get("/api/projects/open-recent")
    with c.session_transaction() as s:
        assert "current_project_path" not in s
