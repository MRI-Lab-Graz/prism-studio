"""Everything DataLad needs is checked together, before DataLad touches the project."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_doctor import datalad_preflight  # noqa: E402
from src.project_settings import save_project_git_identity  # noqa: E402


@pytest.fixture
def clean_git(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    return cfg


def _which_all(name):
    return f"/usr/bin/{name}"


def test_ready_machine_has_no_problems(clean_git, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    save_project_git_identity(proj, "Eva", "eva@uni.example")
    assert datalad_preflight(proj, which=_which_all) == []


def test_on_a_shared_login_a_new_dataset_needs_the_projects_own_identity_even_if_the_machine_has_one(clean_git, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    assert any("none of its own" in p for p in datalad_preflight(proj, which=_which_all))


def test_an_already_tracked_dataset_may_use_the_machines_identity(clean_git, tmp_path):
    proj = tmp_path / "proj"
    (proj / ".datalad").mkdir(parents=True)
    assert datalad_preflight(proj, which=_which_all) == []


def test_every_problem_is_reported_at_once(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    proj = tmp_path / "proj"
    proj.mkdir()
    problems = datalad_preflight(proj, which=lambda n: None if n == "git-annex" else _which_all(n))
    text = "\n".join(problems)
    assert "git-annex" in text and "name and email" in text
    assert len(problems) == 2


def test_project_inside_another_git_repository_is_reported(clean_git, tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path / "outer")], check=True)
    proj = tmp_path / "outer" / "proj"
    proj.mkdir()
    save_project_git_identity(proj, "Eva", "eva@uni.example")
    assert any("inside another git repository" in p for p in datalad_preflight(proj, which=_which_all))


def test_unwritable_project_is_reported(clean_git, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    save_project_git_identity(proj, "Eva", "eva@uni.example")
    proj.chmod(0o500)
    try:
        assert any("write" in p for p in datalad_preflight(proj, which=_which_all))
    finally:
        proj.chmod(0o700)


def test_git_that_cannot_commit_is_reported(clean_git, tmp_path):
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    clean_git.write_text(clean_git.read_text() + f"[core]\n\thooksPath = {hooks}\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    save_project_git_identity(proj, "Eva", "eva@uni.example")
    assert any("test commit" in p for p in datalad_preflight(proj, which=_which_all))


def test_on_a_personal_computer_the_machines_identity_is_enough_for_a_new_dataset(clean_git, tmp_path):
    from src.settings_update import update_app_settings

    update_app_settings(tmp_path, {"shared_login": False})
    proj = tmp_path / "proj"
    proj.mkdir()
    assert datalad_preflight(proj, which=_which_all) == []


def test_a_login_is_shared_until_the_user_says_otherwise():
    from src.config import load_app_settings

    assert load_app_settings().shared_login is True
