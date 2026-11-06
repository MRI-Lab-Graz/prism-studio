"""Put on server: the first person creates the project's dataset on the lab server, then the validated send.

Real DataLad, a local folder as the server (an ssh address is the same `create-sibling` call and cannot be tested here).
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

from src.share_publish import Identity, location_problem, put_on_server, sync_with_server  # noqa: E402

needs_datalad = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)
WHO = Identity("Ada", "ada@example.org")


def _run(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _save(root, name, text="some text\n"):  # a bare "x" is detected as binary and annexed
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _run("datalad", "save", "-m", f"add {name}", cwd=root)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A saved project (DataLad on, no server yet) and where its server will be."""
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    root = tmp_path / "project"
    _run("datalad", "create", "-c", "text2git", str(root), cwd=tmp_path)
    _save(root, "participants.tsv", "participant_id\nsub-01\n")
    return root, tmp_path / "server"


def _put(root, location, errors=(), **kwargs):
    with patch("src.share_publish.validate_for_publish", return_value=list(errors)):
        return put_on_server(root, str(location), identity=WHO, **kwargs)


def _files(repo):
    return _run("git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD", cwd=repo.parent).split()


@needs_datalad
def test_put_on_server_creates_the_dataset_and_sends_it(project):
    root, server = project
    result = _put(root, server)
    assert result["success"] is True and result["reason"] == "pushed", result
    clone = server.parent / "teammate"
    _run("datalad", "clone", str(server), str(clone), cwd=server.parent)
    assert (clone / "participants.tsv").read_text(encoding="utf-8") == "participant_id\nsub-01\n"


@needs_datalad
def test_it_refuses_a_location_that_already_holds_a_dataset(project):
    root, server = project
    _run("datalad", "create", str(server), cwd=server.parent)
    before = sorted(str(p.relative_to(server)) for p in server.rglob("*"))
    head = _run("git", "-C", str(server), "rev-parse", "HEAD", cwd=server.parent)
    result = _put(root, server)
    assert result["success"] is False and result["reason"] == "location_exists", result
    assert "open it from the server" in result["message"].lower()
    assert sorted(str(p.relative_to(server)) for p in server.rglob("*")) == before
    assert _run("git", "-C", str(server), "rev-parse", "HEAD", cwd=server.parent) == head
    assert "origin" not in _run("git", "remote", cwd=root).split()


@needs_datalad
def test_it_refuses_an_invalid_dataset_before_creating_anything_on_the_server(project):
    root, server = project
    result = _put(root, server, errors=["bad name"])
    assert result["success"] is False and result["reason"] == "validation_errors"
    assert result["errors"] == ["bad name"]
    assert not server.exists()
    assert "origin" not in _run("git", "remote", cwd=root).split()


@needs_datalad
def test_an_acknowledged_invalid_dataset_is_put_on_the_server(project):
    root, server = project
    result = _put(root, server, errors=["bad name"], allow_invalid=True)
    assert result["success"] is True and result["reason"] == "pushed_with_errors", result
    assert "participants.tsv" in _files(server)


@needs_datalad
def test_it_refuses_unsaved_changes(project):
    root, server = project
    (root / "draft.txt").write_text("not saved\n", encoding="utf-8")
    result = _put(root, server)
    assert result["success"] is False and result["reason"] == "uncommitted_changes"
    assert not server.exists()


@pytest.mark.parametrize("location", ["https://x/y", "http://x/y", "git://x/y", "-oProxy=x", "", "a\nb"])
def test_it_refuses_web_locations_and_dash_locations(location, tmp_path):
    assert location_problem(location)
    with patch("src.share_publish.run_datalad_create_sibling_plain") as create:
        result = put_on_server(tmp_path, location, identity=WHO)
    assert result["success"] is False and result["reason"] == "bad_location"
    create.assert_not_called()


@pytest.mark.parametrize("location", [
    "ssh://-oX=y@h/p",
    "ssh://u@-oX=y/p",
    "ssh://h x/p",
    "ssh://-oProxyCommand=touch pwned@lab.invalid/x",
    "ssh://-oX=y@/p",
    "-oX=y@h:p",
    "a@-oProxyCommand=x:path",
    "ext::sh -c touch% pwned",
    "datalad-annex::?type=directory",
    "fd::17",
])
def test_an_ssh_option_or_transport_helper_hidden_in_the_location_is_refused(location, tmp_path):
    """ssh gets `[user@]host` without `--` from DataLad: a '-' there would be an ssh option (ProxyCommand runs locally)."""
    assert location_problem(location)
    with patch("src.share_publish.run_datalad_create_sibling_plain") as create:
        assert put_on_server(tmp_path, location, identity=WHO)["reason"] == "bad_location"
    create.assert_not_called()


@pytest.mark.parametrize(
    "location", ["user@host:/srv/x", "ssh://user@host/srv/x", "ssh://host:2222/srv/x", r"C:\share\x", "/srv/lab/project", "../server", "ada@lab.example.org:projects/x", "ssh://lab.example.org/x"]
)
def test_a_windows_drive_path_is_a_folder_not_an_ssh_target(location):
    assert location_problem(location) == ""


@needs_datalad
def test_public_host_with_tracked_sourcedata_is_refused_before_any_command(project):
    root, _ = project
    _save(root, "sourcedata/raw.tsv", "id\tscore\n1\t3\n")
    with patch("src.share_publish.run_datalad_create_sibling_plain") as create:
        result = _put(root, "user@github.com:o/r")
    assert result["success"] is False and result["reason"] == "public_target_with_sourcedata", result
    create.assert_not_called()
    assert "origin" not in _run("git", "remote", cwd=root).split()


@needs_datalad
def test_a_nested_subject_dataset_is_created_recursively(project):
    root, server = project
    _run("datalad", "create", "-c", "text2git", "-d", str(root), str(root / "sub-01"), cwd=root)
    _save(root / "sub-01", "notes.txt", "subject one\n")
    _run("datalad", "save", "-m", "register sub-01", cwd=root)
    result = _put(root, server)
    assert result["success"] is True, result
    assert "notes.txt" in _files(server / "sub-01")


@needs_datalad
def test_a_second_run_after_an_interrupted_put_is_a_sync(project):
    from src.datalad_state import datalad_state

    root, server = project
    with patch("src.share_publish.run_datalad_push", return_value={"success": False, "message": "connection lost"}):
        interrupted = _put(root, server)
    assert interrupted["success"] is False and interrupted["reason"] == "push_failed"
    assert datalad_state(root)["next_step"] == "sync"
    again = _put(root, server)
    assert again["success"] is False and again["reason"] == "has_server"
    assert "sync" in again["message"].lower()
    with patch("src.share_publish.validate_for_publish", return_value=[]):
        synced = sync_with_server(root, identity=WHO)
    assert synced["success"] is True, synced
    assert "participants.tsv" in _files(server)


@needs_datalad
def test_the_cli_and_studio_refuse_the_same_way(project, capsys):
    import src.web.blueprints.projects_datalad_server_blueprint as studio
    from src.cli.commands.datalad import cmd_datalad_put_on_server

    root, server = project
    args = SimpleNamespace(
        project=str(root), location=str(server), sibling_name=None, as_identity=None, json=True, allow_invalid=False
    )
    with patch("src.share_publish.validate_for_publish", return_value=["bad name"]):
        with pytest.raises(SystemExit) as refused:
            cmd_datalad_put_on_server(args)
        cli = json.loads(capsys.readouterr().out)
        studio._create_job("put-refused", kind="put")
        studio._run_put_job("put-refused", root, {"location": str(server)})
        job = studio._get_job("put-refused")
    assert refused.value.code == 1 and job["status"] == "error" and job["kind"] == "put"
    assert cli["reason"] == job["result"]["reason"] == "validation_errors"
    assert cli["errors"] == job["result"]["errors"] == ["bad name"]
    assert not server.exists()


@needs_datalad
def test_the_cli_and_studio_put_a_project_on_the_server_the_same_way(project, tmp_path, capsys):
    import src.web.blueprints.projects_datalad_server_blueprint as studio
    from src.cli.commands.datalad import cmd_datalad_put_on_server

    root, _ = project
    copy = tmp_path / "copy"
    _run("datalad", "clone", str(root), str(copy), cwd=tmp_path)  # identical project, its own (removed) origin
    _run("git", "remote", "remove", "origin", cwd=copy)
    cli_server, studio_server = tmp_path / "cli-server", tmp_path / "studio-server"
    with patch("src.share_publish.validate_for_publish", return_value=[]):
        cmd_datalad_put_on_server(SimpleNamespace(
            project=str(root), location=str(cli_server), sibling_name=None, as_identity=None, json=True, allow_invalid=False,
        ))
        cli = json.loads(capsys.readouterr().out)
        studio._create_job("put-ok", kind="put")
        studio._run_put_job("put-ok", copy, {"location": str(studio_server)})
        job = studio._get_job("put-ok")
    assert job["status"] == "complete", job
    assert cli["reason"] == job["result"]["reason"] == "pushed"
    assert _files(cli_server) == _files(studio_server)


def _prism_tools(*argv):
    """The real entry point (parser, dispatch, handler map): direct handler calls once hid an undispatched command."""
    return subprocess.run([sys.executable, str(ROOT / "prism_tools.py"), *argv], capture_output=True, text=True, timeout=120)


def test_datalad_status_runs_through_the_real_dispatch(tmp_path):
    out = _prism_tools("datalad", "status", "--project", str(tmp_path), "--json")
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["next_step"] in {"enable", "install_datalad"}


def test_put_on_server_runs_through_the_real_dispatch(tmp_path):
    out = _prism_tools("datalad", "put-on-server", "--project", str(tmp_path), "--location", "https://x/y", "--json")
    assert out.returncode == 1, out.stderr
    assert json.loads(out.stdout)["reason"] == "bad_location"


def test_the_cli_parser_has_put_on_server():
    from src.cli.parser import build_prism_tools_parsers

    parser, _ = build_prism_tools_parsers(ROOT / "app")
    args = parser.parse_args([
        "datalad", "put-on-server", "--project", "/p", "--location", "/srv/x", "--allow-invalid", "--json",
    ])
    assert (args.location, args.sibling_name, args.allow_invalid) == ("/srv/x", None, True)


def test_a_home_folder_location_is_checked_where_open_from_server_looks(tmp_path, monkeypatch):
    """`~/x` means the home folder for both commands: a non-empty one is refused, never a literal '~' folder."""
    from src.share_publish import _local_folder_in_use

    home = tmp_path / "home"
    (home / "server" / "study").mkdir(parents=True)
    (home / "server" / "study" / "file.txt").write_text("x\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    project = tmp_path / "project"
    project.mkdir()
    assert _local_folder_in_use(project, "~/server/study") is True
