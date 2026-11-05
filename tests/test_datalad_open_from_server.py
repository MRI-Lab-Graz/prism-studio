"""Open from server: everybody else gets their own copy of the project from the lab server.

Real DataLad, a local folder as the server (made with put-on-server; ssh is the same `datalad clone` call).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_clone import open_from_server  # noqa: E402

needs_datalad = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)


def _run(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _save(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data) if isinstance(data, bytes) else path.write_text(data, encoding="utf-8")
    _run("datalad", "save", "-m", f"add {name}", cwd=root)


def _identity(tmp_path, monkeypatch, text="[user]\n\tname = Ada\n\temail = ada@example.org\n"):
    cfg = tmp_path / "gitconfig"
    cfg.write_text(text)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def server(tmp_path, monkeypatch):
    """A project with a nested subject dataset (text and annexed data), put on a local folder as the lab server."""
    from src.share_publish import Identity, put_on_server

    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    project = tmp_path / "project"
    _run("datalad", "create", "-c", "text2git", str(project), cwd=tmp_path)
    _save(project, "participants.tsv", "participant_id\nsub-01\n")
    _run("datalad", "create", "-c", "text2git", "-d", str(project), str(project / "sub-01"), cwd=project)
    _save(project / "sub-01", "notes.txt", "subject one\n")
    _save(project / "sub-01", "data.bin", bytes(range(256)) * 64)  # binary: annexed
    _run("datalad", "save", "-m", "register sub-01", cwd=project)
    location = tmp_path / "server"
    with patch("src.share_publish.validate_for_publish", return_value=[]):
        put = put_on_server(project, str(location), identity=Identity("Ada", "ada@example.org"))
    assert put["success"] is True, put
    return location


@needs_datalad
def test_open_clones_the_project_into_an_empty_folder(server, tmp_path):
    target = tmp_path / "mine"
    target.mkdir()
    result = open_from_server(str(server), target)
    assert result["success"] is True, result
    assert result["path"] == str(target.resolve())
    assert (target / "participants.tsv").read_text(encoding="utf-8") == "participant_id\nsub-01\n"


@needs_datalad
def test_it_refuses_a_target_that_is_not_empty(server, tmp_path):
    target = tmp_path / "mine"
    target.mkdir()
    (target / "keep.txt").write_text("mine\n", encoding="utf-8")
    result = open_from_server(str(server), target)
    assert result["success"] is False and result["reason"] == "target_not_empty"
    assert sorted(p.name for p in target.iterdir()) == ["keep.txt"]


@pytest.mark.parametrize("location", ["https://x/y", "git://x/y", "-oProxy=x", "ext::sh -c x", ""])
def test_it_refuses_a_web_location(location, tmp_path):
    with patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server(location, tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "bad_location"
    clone.assert_not_called()
    assert not (tmp_path / "mine").exists()


@needs_datalad
def test_the_copy_has_origin_as_its_server(server, tmp_path):
    from src.datalad_state import datalad_state

    result = open_from_server(str(server), tmp_path / "mine")
    assert result["success"] is True, result
    assert datalad_state(tmp_path / "mine")["server"]["name"] == "origin"


@needs_datalad
def test_nested_subject_datasets_are_installed_without_content(server, tmp_path):
    target = tmp_path / "mine"
    assert open_from_server(str(server), target)["success"] is True
    nested = target / "sub-01"
    assert (nested / "notes.txt").read_text(encoding="utf-8") == "subject one\n"
    missing = _run("git", "annex", "find", "--not", "--in=here", cwd=nested).split()
    assert missing == ["data.bin"]


@needs_datalad
def test_the_copy_has_the_save_gate_hook_in_the_project_and_nested_datasets(server, tmp_path):
    from src.save_gate import has_save_hook

    target = tmp_path / "mine"
    result = open_from_server(str(server), target)
    assert result["success"] is True, result
    assert has_save_hook(target) and has_save_hook(target / "sub-01")


@needs_datalad
def test_without_a_git_identity_it_stops_before_cloning(server, tmp_path, monkeypatch):
    _identity(tmp_path, monkeypatch, text="")
    with patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server(str(server), tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "no_identity", result
    clone.assert_not_called()
    assert not (tmp_path / "mine").exists()


def test_without_datalad_it_stops_before_cloning(tmp_path):
    from src.datalad_doctor import datalad_preflight

    no_tools = lambda project: datalad_preflight(project, which=lambda tool: None)  # noqa: E731
    with patch("src.datalad_clone.datalad_preflight", no_tools), patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server("/srv/lab/project", tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "no_datalad", result
    clone.assert_not_called()


def _studio(job_id, location, target):
    import src.web.blueprints.projects_datalad_server_blueprint as studio

    studio._create_ria_job(job_id, kind="open")
    studio._run_open_job(job_id, Path(target), {"location": str(location)})
    return studio._get_ria_job(job_id)


def _cli(location, target, capsys):
    from src.cli.commands.datalad import cmd_datalad_open_from_server

    code = 0
    try:
        cmd_datalad_open_from_server(SimpleNamespace(location=str(location), target=str(target), json=True))
    except SystemExit as exc:
        code = exc.code
    return code, json.loads(capsys.readouterr().out)


@needs_datalad
def test_the_cli_and_studio_refuse_the_same_way(server, tmp_path, capsys):
    for name in ("cli", "studio"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "keep.txt").write_text("mine\n", encoding="utf-8")
    code, cli = _cli(server, tmp_path / "cli", capsys)
    job = _studio("open-refused", server, tmp_path / "studio")
    assert code == 1 and job["status"] == "error" and job["kind"] == "open"
    assert cli["reason"] == job["result"]["reason"] == "target_not_empty"


@needs_datalad
def test_the_cli_and_studio_open_a_project_the_same_way(server, tmp_path, capsys):
    from src.save_gate import has_save_hook

    code, cli = _cli(server, tmp_path / "cli", capsys)
    job = _studio("open-ok", server, tmp_path / "studio")
    assert code == 0 and job["status"] == "complete", job
    assert cli["path"] == str((tmp_path / "cli").resolve())
    assert job["result"]["path"] == str((tmp_path / "studio").resolve())  # the page opens this project
    def files(d):
        return sorted(str(p.relative_to(d)) for p in d.rglob("*") if ".git" not in p.parts)

    assert files(tmp_path / "cli") == files(tmp_path / "studio")
    assert has_save_hook(tmp_path / "studio" / "sub-01") and has_save_hook(tmp_path / "cli" / "sub-01")


def _prism_tools(*argv):
    return subprocess.run([sys.executable, str(ROOT / "prism_tools.py"), *argv], capture_output=True, text=True, timeout=120)


def test_open_from_server_runs_through_the_real_dispatch(tmp_path):
    out = _prism_tools(
        "datalad", "open-from-server", "--location", "https://x/y", "--target", str(tmp_path / "mine"), "--json"
    )
    assert out.returncode == 1, out.stderr
    assert json.loads(out.stdout)["reason"] == "bad_location"
