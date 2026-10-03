"""Save-gate acceptance battery, end to end with real git/DataLad and the real validator.

Two rules, nothing else:

  1. In a DataLad project a change can be saved only if the validator is green.
  2. Without DataLad nothing changes: no hook, no refused commit, no file touched.

The unit tests (test_save_gate_*.py) use fake tools; this battery runs the real
`prism_tools.py save-gate --check` through real commits.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import src.save_gate as sg
from src.share_publish import audit_path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "examples" / "wellbeing_multi_demo"  # a dataset that validates green

needs_datalad = pytest.mark.skipif(
    not (shutil.which("git") and shutil.which("git-annex") and shutil.which("datalad")),
    reason="datalad and git-annex required",
)

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t.t"]


def sh(*args, cwd, env=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, env=env)


def head(root) -> str:
    return sh("git", "rev-parse", "HEAD", cwd=root).stdout.strip()


def snapshot(root: Path) -> dict[str, str]:
    """Every file under root (path -> content hash); .git internals that move on their own excluded."""
    skip = ("index", "logs", "FETCH_HEAD", "ORIG_HEAD", "COMMIT_EDITMSG")
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink() and not (".git" in p.parts and p.name in skip):
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture(autouse=True)
def real_tool(tmp_path, monkeypatch):
    """PRISM_TOOLS -> the real prism_tools.py, run with this interpreter."""
    wrapper = tmp_path / "prism_tools"
    wrapper.write_text(
        f'#!/bin/sh\nPRISM_SKIP_VENV_CHECK=1 exec "{sys.executable}" "{REPO / "prism_tools.py"}" "$@"\n'
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("PRISM_TOOLS", str(wrapper))
    return wrapper


@pytest.fixture
def green(tmp_path):
    """A DataLad dataset holding a valid PRISM dataset, gate installed, first save done."""
    ds = tmp_path / "ds"
    assert sh("datalad", "create", "-c", "text2git", str(ds), cwd=tmp_path).returncode == 0
    shutil.copytree(DEMO, ds, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", ".datalad"))
    assert sg.install_save_hooks(ds)["installed"] == [str(ds)]
    first = sh("datalad", "save", "-m", "scaffold", cwd=ds)
    assert first.returncode == 0, first.stdout + first.stderr
    assert sg.check_save(ds).allowed
    return ds


def commit_all(ds, message="change"):
    sh("git", "add", "-A", cwd=ds)
    return sh(*GIT, "commit", "-m", message, cwd=ds)


def edit_valid(ds):
    path = ds / "dataset_description.json"
    data = json.loads(path.read_text())
    data["Name"] = data.get("Name", "x") + " (edited)"
    path.write_text(json.dumps(data, indent=2))


def break_bad_json(ds):
    (ds / "dataset_description.json").write_text("{ not json")


def break_missing_description(ds):
    (ds / "dataset_description.json").unlink()


def break_no_subjects(ds):
    for sub in ds.glob("sub-*"):
        shutil.rmtree(sub)


BREAKERS = [break_bad_json, break_missing_description, break_no_subjects]


# --------------------------------------------------------------------------- 1. DataLad: green only


@needs_datalad
def test_valid_change_is_saved_with_git_commit(green):
    before = head(green)
    edit_valid(green)
    r = commit_all(green)
    assert r.returncode == 0, r.stderr
    assert head(green) != before


@needs_datalad
def test_valid_change_is_saved_with_datalad_save(green):
    before = head(green)
    edit_valid(green)
    r = sh("datalad", "save", "-m", "edit", cwd=green)
    assert r.returncode == 0, r.stdout + r.stderr
    assert head(green) != before


@needs_datalad
@pytest.mark.parametrize("breaker", BREAKERS, ids=lambda f: f.__name__)
def test_invalid_change_is_refused_by_git_commit(green, breaker):
    before = head(green)
    breaker(green)
    r = commit_all(green)
    assert r.returncode != 0
    assert sg.SAVE_GATE_MARKER in r.stderr
    assert head(green) == before  # nothing was saved


@needs_datalad
@pytest.mark.parametrize("breaker", BREAKERS, ids=lambda f: f.__name__)
def test_invalid_change_is_refused_by_datalad_save(green, breaker):
    before = head(green)
    breaker(green)
    r = sh("datalad", "save", "-m", "bad", cwd=green)
    assert r.returncode != 0
    assert sg.SAVE_GATE_MARKER in r.stdout + r.stderr
    assert head(green) == before


@needs_datalad
def test_commit_dash_a_cannot_smuggle_an_invalid_change(green):
    before = head(green)
    break_bad_json(green)
    r = sh(*GIT, "commit", "-a", "-m", "bad", cwd=green)
    assert r.returncode != 0 and head(green) == before


@needs_datalad
def test_refused_change_stays_in_the_working_tree_so_it_can_be_fixed(green):
    original = (green / "dataset_description.json").read_text()
    break_bad_json(green)
    assert commit_all(green).returncode != 0
    assert (green / "dataset_description.json").read_text() == "{ not json"  # not reverted, not lost
    (green / "dataset_description.json").write_text(original)
    assert commit_all(green).returncode != 0  # back to the saved state: nothing left to commit
    edit_valid(green)
    before = head(green)
    r = commit_all(green, "fixed")
    assert r.returncode == 0 and head(green) != before


@needs_datalad
def test_while_the_tree_is_red_even_an_unrelated_file_cannot_be_saved(green):
    before = head(green)
    break_bad_json(green)
    (green / "notes.txt").write_text("harmless")
    sh("git", "add", "notes.txt", cwd=green)
    r = sh(*GIT, "commit", "-m", "notes only", "-o", "notes.txt", cwd=green)
    assert r.returncode != 0 and head(green) == before


@needs_datalad
def test_amend_is_gated_too(green):
    edit_valid(green)
    assert commit_all(green).returncode == 0
    before = head(green)
    break_bad_json(green)
    sh("git", "add", "-A", cwd=green)
    r = sh(*GIT, "commit", "--amend", "--no-edit", cwd=green)
    assert r.returncode != 0 and head(green) == before


@needs_datalad
def test_only_the_first_save_of_a_new_dataset_is_exempt(tmp_path):
    ds = tmp_path / "fresh"
    assert sh("datalad", "create", str(ds), cwd=tmp_path).returncode == 0  # exactly one commit
    sg.install_save_hooks(ds)
    (ds / "scaffold.txt").write_text("an empty scaffold cannot validate")
    assert sh("datalad", "save", "-m", "scaffold", cwd=ds).returncode == 0  # exempt
    (ds / "more.txt").write_text("second save")
    r = sh("datalad", "save", "-m", "second", cwd=ds)
    assert r.returncode != 0 and sg.SAVE_GATE_MARKER in r.stdout + r.stderr  # gated, dataset is red


@needs_datalad
def test_gate_fails_closed_when_prism_tools_is_missing(green, monkeypatch):
    monkeypatch.setenv("PRISM_TOOLS", "/nonexistent/prism_tools")
    before = head(green)
    edit_valid(green)  # a perfectly valid change
    r = commit_all(green)
    assert r.returncode != 0 and "not found" in r.stderr and head(green) == before


@needs_datalad
def test_gate_fails_closed_when_the_checker_crashes(green, tmp_path, monkeypatch):
    crash = tmp_path / "crash"
    crash.write_text("#!/bin/sh\necho boom >&2\nexit 3\n")
    crash.chmod(0o755)
    monkeypatch.setenv("PRISM_TOOLS", str(crash))
    before = head(green)
    edit_valid(green)
    assert commit_all(green).returncode != 0 and head(green) == before


@needs_datalad
def test_every_decision_is_audited(green):
    log = audit_path(green)
    edit_valid(green)
    assert commit_all(green).returncode == 0
    break_bad_json(green)
    assert commit_all(green, "bad").returncode != 0
    lines = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    results = [entry["result"] for entry in lines]
    assert "save_allowed" in results and "save_refused" in results


@needs_datalad
def test_a_real_prism_project_gets_the_gate_and_refuses_a_red_save(tmp_path):
    """The project-creation flow itself installs the hook (not just the test fixture)."""
    sys.path.insert(0, str(REPO / "app"))
    from src.project_manager import ProjectManager

    project = tmp_path / "proj"
    result = ProjectManager().create_project(str(project), {"name": "proj", "use_datalad": True})
    assert result["success"], result
    assert sg.has_save_hook(project)
    before = head(project)
    (project / "README.md").write_text("a fresh project has no subjects yet, so it is red")
    r = commit_all(project)
    assert r.returncode != 0 and head(project) == before


# --------------------------------------------------------------------------- 2. No DataLad: nothing changes


def test_plain_folder_is_left_untouched(tmp_path):
    folder = tmp_path / "plain"
    shutil.copytree(DEMO, folder, ignore=shutil.ignore_patterns(".git", ".datalad"))
    before = snapshot(folder)
    result = sg.install_save_hooks(folder)
    assert result["installed"] == [] and result["errors"]  # reported, not forced
    assert not (folder / ".git").exists()
    assert snapshot(folder) == before


def test_project_created_without_datalad_has_no_git_and_no_gate(tmp_path):
    sys.path.insert(0, str(REPO / "app"))
    from src.project_manager import ProjectManager

    project = tmp_path / "nodl"
    result = ProjectManager().create_project(str(project), {"name": "nodl", "use_datalad": False})
    assert result["success"], result
    assert not (project / ".git").exists() and not (project / ".datalad").exists()
    assert not result.get("save_gate_hook")


def test_plain_git_repo_commits_invalid_data_exactly_as_before(tmp_path):
    repo = tmp_path / "git_only"
    shutil.copytree(DEMO, repo, ignore=shutil.ignore_patterns(".git", ".datalad"))
    assert sh("git", "init", "-q", cwd=repo).returncode == 0
    assert commit_all(repo, "first").returncode == 0
    break_bad_json(repo)
    before = head(repo)
    r = commit_all(repo, "invalid is fine here")
    assert r.returncode == 0 and head(repo) != before
    assert not sg.has_save_hook(repo)
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


def test_status_and_check_never_install_or_modify_anything(tmp_path, real_tool):
    repo = tmp_path / "git_only"
    shutil.copytree(DEMO, repo, ignore=shutil.ignore_patterns(".git", ".datalad"))
    sh("git", "init", "-q", cwd=repo)
    commit_all(repo, "first")
    before = snapshot(repo)
    status = sh(str(real_tool), "save-gate", "--status", "--project", str(repo), cwd=tmp_path)
    assert status.returncode == 0 and "NO HOOK" in status.stdout
    sh(str(real_tool), "save-gate", "--check", "--project", str(repo), cwd=tmp_path)
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()
    assert {k: v for k, v in snapshot(repo).items() if not k.startswith(".git/prism")} == {
        k: v for k, v in before.items() if not k.startswith(".git/prism")
    }


def test_foreign_pre_commit_hook_is_never_overwritten(tmp_path):
    repo = tmp_path / "git_only"
    repo.mkdir()
    sh("git", "init", "-q", cwd=repo)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n# someone else's hook\nexit 0\n")
    hook.chmod(0o755)
    before = hook.read_bytes()
    result = sg.install_save_hooks(repo)
    assert result["installed"] == [] and result["foreign"] == [str(repo)]
    assert hook.read_bytes() == before


def test_the_validator_never_modifies_the_dataset_it_checks(tmp_path):
    ds = tmp_path / "ds"
    shutil.copytree(DEMO, ds, ignore=shutil.ignore_patterns(".git", ".datalad"))
    before = snapshot(ds)
    env = {**os.environ, "PRISM_SKIP_VENV_CHECK": "1"}
    r = sh(sys.executable, str(REPO / "app" / "prism.py"), str(ds), cwd=tmp_path, env=env)
    assert r.returncode in (0, 1), r.stderr
    assert snapshot(ds) == before
