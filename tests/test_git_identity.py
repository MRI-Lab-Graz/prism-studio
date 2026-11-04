"""DataLad needs a git name + email: checked up front, set from one function (CLI + Studio Settings)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_doctor import get_git_identity, set_git_identity  # noqa: E402


@pytest.fixture
def no_identity(tmp_path, monkeypatch):
    """A fresh machine: empty global git config, no system config, no identity in the environment."""
    cfg = tmp_path / "gitconfig"
    cfg.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(var, raising=False)
    return cfg


def test_identity_is_empty_on_a_fresh_machine(no_identity):
    assert get_git_identity() == {"name": "", "email": ""}


def test_set_identity_is_read_back(no_identity):
    set_git_identity("Ada Lovelace", "ada@example.org")
    assert get_git_identity() == {"name": "Ada Lovelace", "email": "ada@example.org"}


@pytest.mark.parametrize("name, email", [("", "a@b.org"), ("Ada", ""), ("Ada", "not-an-email"), ("A\nda", "a@b.org")])
def test_set_identity_refuses_incomplete_values(no_identity, name, email):
    with pytest.raises(ValueError):
        set_git_identity(name, email)
    assert get_git_identity() == {"name": "", "email": ""}


def test_enable_datalad_stops_before_touching_the_project_without_identity(no_identity, tmp_path):
    from src.project_manager import ProjectManager

    project = tmp_path / "proj"
    project.mkdir()
    result = ProjectManager().enable_datalad_for_project(project)
    assert result["success"] is False
    assert "name and email" in result["error"]
    assert result["needs_git_identity"] is True
    assert not (project / ".git").exists()


def test_cli_identity_sets_and_shows(no_identity, capsys):
    import src.cli.commands.datalad as cli

    cli.cmd_datalad_identity(SimpleNamespace(name="Ada", email="ada@example.org", json=True))
    assert json.loads(capsys.readouterr().out)["email"] == "ada@example.org"
    cli.cmd_datalad_identity(SimpleNamespace(name=None, email=None, json=True))
    assert json.loads(capsys.readouterr().out) == {"success": True, "name": "Ada", "email": "ada@example.org"}


def test_cli_identity_rejects_a_bad_email(no_identity, capsys):
    import src.cli.commands.datalad as cli

    with pytest.raises(SystemExit):
        cli.cmd_datalad_identity(SimpleNamespace(name="Ada", email="nope", json=False))


def test_settings_route_sets_and_reads_identity_without_a_project(no_identity):
    from flask import Flask

    from src.web.blueprints.projects_library_blueprint import projects_library_bp

    app = Flask(__name__)
    app.register_blueprint(projects_library_bp)
    client = app.test_client()
    assert client.get("/api/settings/git-identity").get_json() == {"success": True, "name": "", "email": ""}
    bad = client.post("/api/settings/git-identity", json={"name": "Ada", "email": "nope"})
    assert bad.status_code == 400 and bad.get_json()["success"] is False
    ok = client.post("/api/settings/git-identity", json={"name": "Ada", "email": "ada@example.org"})
    assert ok.get_json() == {"success": True, "name": "Ada", "email": "ada@example.org"}
    assert get_git_identity()["email"] == "ada@example.org"


def test_on_a_personal_computer_the_missing_identity_is_set_in_settings_not_per_project(no_identity, tmp_path):
    from src.project_manager import ProjectManager
    from src.settings_update import update_app_settings

    update_app_settings(tmp_path, {"shared_login": False})
    project = tmp_path / "proj"
    project.mkdir()
    result = ProjectManager().enable_datalad_for_project(project)
    assert result["success"] is False
    assert result["needs_git_identity"] is False
    assert "Settings" in result["error"]
