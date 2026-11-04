"""A project carries its own git name + email (.prismrc.json), so students sharing one login stay apart."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_doctor import datalad_preflight  # noqa: E402
from src.project_settings import (  # noqa: E402
    apply_project_git_identity,
    project_git_identity_env,
    save_project_git_identity,
)


@pytest.fixture
def empty_global_git(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tuseConfigOnly = true\n")  # like Fedora: git never guesses a name from the host
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    return root


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


def test_save_writes_the_identity_into_the_project_config(empty_global_git, project):
    save_project_git_identity(project, "Eva Student", "eva@uni.example")
    saved = json.loads((project / ".prismrc.json").read_text())
    assert (saved["gitUserName"], saved["gitUserEmail"]) == ("Eva Student", "eva@uni.example")


def test_save_refuses_a_bad_email_and_writes_nothing(empty_global_git, project):
    with pytest.raises(ValueError):
        save_project_git_identity(project, "Eva", "nope")
    assert not (project / ".prismrc.json").exists()


def test_identity_is_set_in_the_project_and_every_nested_dataset(empty_global_git, project):
    for repo in (project, project / "sub-01", project / "derivatives" / "x"):
        repo.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
    save_project_git_identity(project, "Eva Student", "eva@uni.example")
    for repo in (project, project / "sub-01", project / "derivatives" / "x"):
        assert _git(repo, "config", "--local", "user.email") == "eva@uni.example"


def test_env_sets_git_variables_and_restores_them(empty_global_git, project, monkeypatch):
    save_project_git_identity(project, "Eva Student", "eva@uni.example")
    with project_git_identity_env(project):
        assert os.environ["GIT_AUTHOR_EMAIL"] == os.environ["GIT_COMMITTER_EMAIL"] == "eva@uni.example"
    assert "GIT_AUTHOR_EMAIL" not in os.environ


def test_env_does_nothing_for_a_project_without_identity(empty_global_git, project):
    with project_git_identity_env(project):
        assert "GIT_AUTHOR_NAME" not in os.environ


def test_preflight_accepts_the_projects_identity_when_git_has_none(empty_global_git, project):
    which = lambda n: f"/usr/bin/{n}"  # noqa: E731
    assert any("name and email" in p for p in datalad_preflight(project, which=which))
    save_project_git_identity(project, "Eva Student", "eva@uni.example")
    assert datalad_preflight(project, which=which) == []


@pytest.mark.skipif(not (shutil.which("datalad") and shutil.which("git-annex")), reason="needs datalad + git-annex")
def test_datalad_enable_signs_with_the_projects_identity_and_not_the_machines(empty_global_git, project):
    from src.project_manager import ProjectManager

    (project / "dataset_description.json").write_text('{"Name": "x", "BIDSVersion": "1.10.0"}')
    save_project_git_identity(project, "Eva Student", "eva@uni.example")
    result = ProjectManager().enable_datalad_for_project(project)
    assert result["success"], result
    assert _git(project, "log", "-1", "--format=%an <%ae>") == "Eva Student <eva@uni.example>"
    assert _git(project, "config", "--local", "user.email") == "eva@uni.example"


def test_cli_sets_and_shows_the_projects_identity(empty_global_git, project, capsys):
    import src.cli.commands.datalad as cli

    cli.cmd_datalad_identity(SimpleNamespace(name="Eva", email="eva@uni.example", project=str(project), json=True))
    capsys.readouterr()
    cli.cmd_datalad_identity(SimpleNamespace(name=None, email=None, project=str(project), json=True))
    assert json.loads(capsys.readouterr().out) == {"success": True, "name": "Eva", "email": "eva@uni.example"}


def test_route_sets_and_shows_the_projects_identity(empty_global_git, project):
    from flask import Flask

    from src.web.blueprints.projects_datalad_server_blueprint import projects_datalad_server_bp

    app = Flask(__name__)
    app.register_blueprint(projects_datalad_server_bp)
    client = app.test_client()
    body = {"project_path": str(project), "name": "Eva", "email": "eva@uni.example"}
    assert client.post("/api/projects/git-identity", json=body).get_json()["success"] is True
    got = client.get("/api/projects/git-identity", query_string={"project_path": str(project)}).get_json()
    assert (got["name"], got["email"]) == ("Eva", "eva@uni.example")


@pytest.mark.skipif(not (shutil.which("datalad") and shutil.which("git-annex")), reason="needs datalad + git-annex")
def test_enabling_datalad_keeps_session_logs_and_the_pseudonym_map_out_of_git(empty_global_git, project):
    from src.project_manager import ProjectManager

    (project / "dataset_description.json").write_text('{"Name": "x", "BIDSVersion": "1.10.0"}')
    (project / "code" / "logs").mkdir(parents=True)
    (project / "code" / "logs" / "prism_session_1.log").write_text("/Users/eva/secret/path\n")
    (project / "code" / "anonymization_map.json").write_text("{}")
    (project / "code" / "keep.py").write_text("print(1)\n")
    save_project_git_identity(project, "Eva Student", "eva@uni.example")
    assert ProjectManager().enable_datalad_for_project(project)["success"]
    tracked = _git(project, "ls-files", "code").splitlines()
    assert "code/keep.py" in tracked
    assert not [f for f in tracked if f.startswith("code/logs") or f.endswith("anonymization_map.json")]
