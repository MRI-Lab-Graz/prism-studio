"""Sync = get the latest, then push, and only a valid dataset is pushed (real DataLad, a server folder as the server)."""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.share_publish import Identity, sync_with_server  # noqa: E402

pytestmark = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)
WHO = Identity("Ada", "ada@example.org")


def _run(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def lab(tmp_path, monkeypatch):
    """A server folder, and two users' own copies (cloned from it, so the server is their 'origin')."""
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    first, server = tmp_path / "first", tmp_path / "server"
    _run("datalad", "create", "-c", "text2git", str(first), cwd=tmp_path)
    _run("datalad", "create-sibling", str(server), "-s", "origin", cwd=first)
    _run("datalad", "push", "--to", "origin", cwd=first)
    mine, other = tmp_path / "mine", tmp_path / "other"
    for copy in (mine, other):
        _run("datalad", "clone", str(server), str(copy), cwd=tmp_path)
    return server, mine, other


def _save(root, name, text="some text\n"):  # a bare "x" is detected as binary and annexed
    (root / name).write_text(text, encoding="utf-8")
    _run("datalad", "save", "-m", f"add {name}", cwd=root)


def _server_files(server):
    return _run("git", "-C", str(server), "ls-tree", "-r", "--name-only", "HEAD", cwd=server.parent).split()


def _sync(root, errors=()):
    with patch("src.share_publish.validate_for_publish", return_value=list(errors)):
        return sync_with_server(root, identity=WHO)


def test_sync_sends_my_saved_changes_to_the_server(lab):
    server, mine, _ = lab
    _save(mine, "mine.txt")
    result = _sync(mine)
    assert result["success"] is True, result
    assert "mine.txt" in _server_files(server)


def test_sync_brings_in_what_somebody_else_saved(lab):
    server, mine, other = lab
    _save(other, "theirs.txt")
    assert _sync(other)["success"] is True
    result = _sync(mine)
    assert result["success"] is True, result
    assert (mine / "theirs.txt").exists()


def test_when_both_changed_nothing_is_merged_and_nothing_is_pushed(lab):
    server, mine, other = lab
    _save(other, "theirs.txt")
    assert _sync(other)["success"] is True
    _save(mine, "mine.txt")
    result = _sync(mine)
    assert result["success"] is False and result["reason"] == "update_failed"
    assert not (mine / "theirs.txt").exists() and "mine.txt" not in _server_files(server)


def test_an_invalid_dataset_is_never_sent(lab):
    server, mine, _ = lab
    _save(mine, "mine.txt")
    result = _sync(mine, errors=["bad name"])
    assert result["success"] is False and result["reason"] == "validation_errors"
    assert "mine.txt" not in _server_files(server)


def test_sync_refuses_while_there_are_unsaved_changes(lab):
    server, mine, other = lab
    _save(other, "theirs.txt")
    assert _sync(other)["success"] is True
    (mine / "draft.txt").write_text("x", encoding="utf-8")
    result = _sync(mine)
    assert result["success"] is False and "unsaved" in result["message"].lower()
    assert not (mine / "theirs.txt").exists()


def test_sync_without_a_server_says_to_put_the_project_on_it_first(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("HOME", str(tmp_path))
    lonely = tmp_path / "lonely"
    _run("datalad", "create", str(lonely), cwd=tmp_path)
    result = _sync(lonely)
    assert result["success"] is False and result["reason"] == "no_sibling"


def test_the_cli_and_studio_refuse_an_invalid_dataset_the_same_way(lab, capsys):
    import json
    from types import SimpleNamespace

    import src.web.blueprints.projects_datalad_server_blueprint as studio
    from src.cli.commands.datalad import cmd_datalad_sync

    server, mine, other = lab
    for root in (mine, other):
        _save(root, f"{root.name}.txt")
    with patch("src.share_publish.validate_for_publish", return_value=["bad name"]):
        with pytest.raises(SystemExit) as refused:
            cmd_datalad_sync(SimpleNamespace(project=str(mine), sibling_name=None, as_identity="Ada <ada@example.org>", json=True))
        cli = json.loads(capsys.readouterr().out)
        studio._create_job("parity", kind="sync")
        studio._run_sync_job("parity", other, {})
        job = studio._get_job("parity")
    assert refused.value.code == 1 and job["status"] == "error"
    assert cli["reason"] == job["result"]["reason"] == "validation_errors"
    assert cli["errors"] == job["result"]["errors"] == ["bad name"]
    assert not {"mine.txt", "other.txt"} & set(_server_files(server))


def test_the_cli_and_studio_send_an_acknowledged_invalid_dataset_the_same_way(lab, capsys):
    import json
    from types import SimpleNamespace

    import src.web.blueprints.projects_datalad_server_blueprint as studio
    from src.cli.commands.datalad import cmd_datalad_sync

    server, mine, other = lab
    _save(mine, "mine.txt")
    with patch("src.share_publish.validate_for_publish", return_value=["bad name"]):
        cmd_datalad_sync(SimpleNamespace(
            project=str(mine), sibling_name=None, as_identity="Ada <ada@example.org>", json=True, allow_invalid=True,
        ))
        cli = json.loads(capsys.readouterr().out)
    assert _sync(other)["success"] is True  # other gets mine.txt first (sync never merges)
    _save(other, "other.txt")
    with patch("src.share_publish.validate_for_publish", return_value=["bad name"]):
        studio._create_job("ack", kind="sync")
        studio._run_sync_job("ack", other, {"allow_invalid": True})
        job = studio._get_job("ack")
    assert job["status"] == "complete", job
    assert cli["reason"] == job["result"]["reason"] == "pushed_with_errors"
    assert cli["errors"] == job["result"]["errors"] == ["bad name"]
    assert {"mine.txt", "other.txt"} <= set(_server_files(server))


def _add_subject(root, name="sub-03"):
    """A new nested subject dataset with a text file, registered in the parent (as `datalad enable` does)."""
    _run("datalad", "create", "-c", "text2git", "-d", ".", name, cwd=root)
    (root / name / "notes.txt").write_text("new subject\n", encoding="utf-8")
    _run("datalad", "save", "-r", "-m", f"add {name}", cwd=root)


def test_a_subject_added_after_the_server_reaches_it_with_sync(lab, tmp_path):
    from src.datalad_clone import open_from_server

    server, mine, _ = lab
    _add_subject(mine)
    result = _sync(mine)
    assert result["success"] is True, result
    assert "sub-03" in _server_files(server)
    teammate = tmp_path / "teammate"
    opened = open_from_server(str(server), teammate)
    assert opened["success"] is True, opened
    assert (teammate / "sub-03" / "notes.txt").read_text(encoding="utf-8") == "new subject\n"


def test_a_refused_sync_creates_nothing_on_the_server(lab):
    server, mine, _ = lab
    _add_subject(mine)
    result = _sync(mine, errors=["bad name"])
    assert result["success"] is False and result["reason"] == "validation_errors"
    assert not (server / "sub-03").exists()


def test_a_failed_update_that_is_not_a_divergence_does_not_blame_two_people(lab):
    from src.project_manager import ProjectManager

    server, mine, _ = lab
    _run("git", "remote", "set-url", "origin", str(server.parent / "gone"), cwd=mine)
    result = ProjectManager().update_datalad_from_server(mine)
    assert result["success"] is False
    assert "both saved" not in result["error"]



def test_get_latest_with_a_subject_that_is_not_on_the_server_yet_is_not_an_error(lab):
    from src.project_manager import ProjectManager

    _, mine, _ = lab
    _add_subject(mine)  # sub-03 has no server copy until the next sync, so there is nothing to get for it
    result = ProjectManager().update_datalad_from_server(mine)
    assert result["success"] is True, result
