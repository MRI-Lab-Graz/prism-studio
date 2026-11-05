"""`datalad status`: what the DataLad page shows next, decided in the backend (the page only renders it)."""

import json
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

from src.datalad_state import datalad_state  # noqa: E402

pytestmark = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)


def _run(*cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def _git_identity(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / "mine"
    _run("datalad", "create", "-c", "text2git", str(root), cwd=tmp_path)
    return root


@pytest.fixture
def with_server(dataset, tmp_path):
    server = tmp_path / "server"
    _run("datalad", "create", "-c", "text2git", str(server), cwd=tmp_path)
    _run("git", "remote", "add", "origin", str(server), cwd=dataset)
    return dataset


def test_next_step_enable_when_not_a_dataset(tmp_path):
    state = datalad_state(tmp_path)
    assert state["enabled"] is False and state["next_step"] == "enable" and state["server"] is None


def test_next_step_put_on_server_when_dataset_has_no_origin(dataset):
    state = datalad_state(dataset)
    assert state["enabled"] and state["server"] is None and state["next_step"] == "put_on_server"


def test_next_step_save_when_unsaved_changes_and_server(with_server):
    (with_server / "notes.txt").write_text("hello\n", encoding="utf-8")
    state = datalad_state(with_server)
    assert state["unsaved_count"] == 1 and state["next_step"] == "save"
    assert state["server"]["name"] == "origin" and state["server"]["reachable"] is None  # not asked


def test_next_step_sync_when_clean_and_server(with_server):
    state = datalad_state(with_server, check_server=True)
    assert state["unsaved_count"] == 0 and state["next_step"] == "sync"
    assert state["server"]["reachable"] is True


def test_an_unreachable_server_is_reported_not_raised(with_server, tmp_path):
    _run("git", "remote", "set-url", "origin", str(tmp_path / "gone"), cwd=with_server)
    state = datalad_state(with_server, check_server=True)
    assert state["server"]["reachable"] is False and state["next_step"] == "sync"


def test_a_server_not_called_origin_is_reported_with_its_name(dataset, tmp_path):
    _run("git", "remote", "add", "ria-store", str(tmp_path / "x"), cwd=dataset)
    state = datalad_state(dataset)
    assert state["other_servers"] == ["ria-store"] and state["server"] is None
    assert state["next_step"] == "put_on_server"


def test_validate_flag_adds_error_count(with_server, monkeypatch):
    import src.datalad_state as mod

    assert "valid" not in datalad_state(with_server)
    monkeypatch.setattr(mod, "validate_for_publish", lambda root: ["a", "b"])
    state = datalad_state(with_server, validate=True)
    assert state["valid"] is False and state["error_count"] == 2


def test_cli_json_and_the_route_answer_the_same(with_server, capsys, monkeypatch):
    import src.web.blueprints.projects as projects
    from flask import Flask
    from src.cli.commands.datalad import cmd_datalad_status

    cmd_datalad_status(SimpleNamespace(project=str(with_server), json=True, check_server=True, validate=False))
    cli = json.loads(capsys.readouterr().out)
    monkeypatch.setattr(projects, "get_current_project", lambda: {"path": str(with_server)})
    with Flask(__name__).test_request_context("/api/projects/datalad/state?check_server=1"):
        body = projects.datalad_state_route().get_json()
    assert body == cli
