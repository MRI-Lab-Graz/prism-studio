"""'Get latest': a project updates from the server's newest saved state, and only when that is safe."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.project_manager import ProjectManager  # noqa: E402

pytestmark = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)


def _run(*cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def two_copies(tmp_path, monkeypatch):
    """`server` (a saved dataset) and `mine`, a clone of it whose sibling is called 'origin'."""
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    server, mine = tmp_path / "server", tmp_path / "mine"
    _run("datalad", "create", "-c", "text2git", str(server), cwd=tmp_path)  # text stays in git, as in PRISM projects
    _run("datalad", "clone", str(server), str(mine), cwd=tmp_path)
    return server, mine


def _server_saves(server, name="news.txt"):
    (server / name).write_text("new", encoding="utf-8")
    _run("datalad", "save", "-m", f"add {name}", cwd=server)


def _update(mine, **kwargs):
    return ProjectManager().update_datalad_from_server(mine, sibling_name="origin", **kwargs)


def test_get_latest_brings_in_what_the_server_has_saved(two_copies):
    server, mine = two_copies
    _server_saves(server)
    result = _update(mine)
    assert result["success"] is True and result["updated"] is True
    assert (mine / "news.txt").read_text() == "new"


def test_get_latest_when_already_current_says_so(two_copies):
    _, mine = two_copies
    result = _update(mine)
    assert result["success"] is True and result["updated"] is False


def test_get_latest_never_touches_unsaved_changes(two_copies):
    server, mine = two_copies
    _server_saves(server)
    (mine / "draft.txt").write_text("mine", encoding="utf-8")
    result = _update(mine)
    assert result["success"] is False and "unsaved" in result["error"].lower()
    assert not (mine / "news.txt").exists() and (mine / "draft.txt").exists()


def test_get_latest_refuses_instead_of_merging_when_both_changed(two_copies):
    server, mine = two_copies
    _server_saves(server)
    (mine / "mine.txt").write_text("mine", encoding="utf-8")
    _run("datalad", "save", "-m", "my change", cwd=mine)
    result = _update(mine)
    assert result["success"] is False
    assert not (mine / "news.txt").exists() and (mine / "mine.txt").exists()


def test_a_project_without_a_server_is_skipped_not_an_error(two_copies):
    _, mine = two_copies
    result = ProjectManager().update_datalad_from_server(mine, sibling_name="not-there")
    assert result["success"] is True and result["skipped"] is True


def test_a_project_without_datalad_is_refused(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    result = ProjectManager().update_datalad_from_server(plain)
    assert result["success"] is False
