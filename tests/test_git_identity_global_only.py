"""The git name and email belong to the person (global git config), never to the project.

A project is shared by several users, each with their own copy: an identity inside the project file would travel
with every push and pull and sign one person's snapshots with another person's name.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.config import AppSettings, load_config, save_config  # noqa: E402
from src.datalad_doctor import datalad_preflight  # noqa: E402


def _which_all(name):
    return f"/usr/bin/{name}"


def _global_git(key):
    out = subprocess.run(["git", "config", "--global", key], capture_output=True, text=True)
    return out.stdout.strip()


@pytest.fixture
def git_home(tmp_path, monkeypatch):
    """A global git config we control; pass identity=... to pre-fill it."""
    cfg = tmp_path / "gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    return cfg


def _legacy_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".prismrc.json").write_text(
        json.dumps({"gitUserName": "Eva", "gitUserEmail": "eva@uni.example", "siblingName": "ria-store"})
    )
    return proj


def test_project_config_carries_no_identity(tmp_path):
    proj = _legacy_project(tmp_path)
    config = load_config(str(proj))
    assert not hasattr(config, "git_user_name") and not hasattr(config, "git_user_email")
    save_config(config, str(proj))
    assert "gitUserName" not in json.loads((proj / ".prismrc.json").read_text())


def test_there_is_no_shared_login_setting():
    assert not hasattr(AppSettings(), "shared_login")


def test_an_old_project_identity_moves_to_the_computer_when_it_has_none(git_home, tmp_path):
    git_home.write_text("")
    proj = _legacy_project(tmp_path)
    assert datalad_preflight(proj, which=_which_all) == []
    assert (_global_git("user.name"), _global_git("user.email")) == ("Eva", "eva@uni.example")
    assert "gitUserName" not in json.loads((proj / ".prismrc.json").read_text())


def test_an_old_project_identity_never_replaces_the_computers(git_home, tmp_path):
    git_home.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    proj = _legacy_project(tmp_path)
    assert datalad_preflight(proj, which=_which_all) == []
    assert _global_git("user.name") == "Ada"
    assert "gitUserName" not in json.loads((proj / ".prismrc.json").read_text())


def test_an_unreadable_project_file_does_not_stop_the_check(git_home, tmp_path):
    git_home.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".prismrc.json").write_text("{not json")
    assert datalad_preflight(proj, which=_which_all) == []
    assert (proj / ".prismrc.json").read_text() == "{not json"


def test_a_new_project_uses_the_computers_identity(git_home, tmp_path):
    git_home.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    assert datalad_preflight(proj, which=_which_all) == []


def test_without_any_identity_the_fix_is_the_global_one(git_home, tmp_path):
    git_home.write_text("")
    proj = tmp_path / "proj"
    proj.mkdir()
    (problem,) = datalad_preflight(proj, which=_which_all)
    assert "datalad identity --name" in problem and "--project" not in problem
