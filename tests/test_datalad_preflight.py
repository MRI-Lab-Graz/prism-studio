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
    assert datalad_preflight(proj, which=_which_all) == []




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
    assert any("inside another git repository" in p for p in datalad_preflight(proj, which=_which_all))


def test_unwritable_project_is_reported(clean_git, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
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
    assert any("test commit" in p for p in datalad_preflight(proj, which=_which_all))






def _project_with_subjects(tmp_path, listed):
    from src.project_manager import ProjectManager

    proj = tmp_path / "proj"
    assert ProjectManager().create_project(str(proj), {"name": "proj", "use_datalad": False})["success"]
    for sub in ("sub-001", "sub-002"):
        survey = proj / sub / "ses-1" / "survey"
        survey.mkdir(parents=True)
        (survey / f"{sub}_ses-1_task-x_survey.tsv").write_text("a\tb\n1\t2\n")
    (proj / "participants.tsv").write_text("participant_id\n" + "".join(f"{s}\n" for s in listed))
    return proj


def test_a_project_that_does_not_validate_is_not_ready_for_datalad(clean_git, tmp_path):
    proj = _project_with_subjects(tmp_path, ["sub-001"])  # sub-002 has a folder but no row
    problems = datalad_preflight(proj, which=_which_all, validate=True)
    assert len(problems) == 1 and "does not validate" in problems[0] and "sub-002" in problems[0]


def test_participants_without_a_folder_do_not_stop_datalad(clean_git, tmp_path):
    proj = _project_with_subjects(tmp_path, ["sub-001", "sub-002", "sub-003"])  # sub-003: screened, no folder
    problems = datalad_preflight(proj, which=_which_all, validate=True)
    assert not any("participants.tsv" in p for p in problems)  # (the fixture's missing sidecars are another error)


def test_enable_refuses_an_invalid_project_and_leaves_it_untouched(clean_git, tmp_path):
    from src.project_manager import ProjectManager

    proj = _project_with_subjects(tmp_path, ["sub-001"])
    result = ProjectManager().enable_datalad_for_project(proj)
    assert result["success"] is False and "does not validate" in result["error"]
    assert not (proj / ".git").exists()


def test_a_new_empty_project_may_still_get_datalad(clean_git, tmp_path):
    from src.project_manager import ProjectManager

    proj = tmp_path / "empty"
    assert ProjectManager().create_project(str(proj), {"name": "empty", "use_datalad": False})["success"]
    assert datalad_preflight(proj, which=_which_all, validate=True) == []
