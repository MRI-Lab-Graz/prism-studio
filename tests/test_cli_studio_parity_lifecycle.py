"""Studio only triggers what the CLI runs: delete a project, enable DataLad, save a DataLad snapshot.

Same shape as test_cli_studio_parity.py: the command and Studio's real handler run on identical projects.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_cli_studio_parity import _studio_json, _two_projects

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def test_deleting_a_project_removes_the_same_folder_and_refuses_the_same_way(tmp_path, monkeypatch, capsys):
    import src.web.blueprints.projects_lifecycle_handlers as lifecycle
    from src.cli.commands.project import cmd_project_delete

    monkeypatch.setattr(lifecycle, "_load_recent_projects", lambda: [])  # the user's real recent list stays untouched
    monkeypatch.setattr(lifecycle, "_save_recent_projects", lambda projects: projects)

    def studio_delete(root, name):
        return _studio_json(
            lifecycle.handle_delete_project, {"path": str(root), "confirm_name": name},
            project_manager=None, get_current_project=lambda: {}, clear_current_project=lambda: None,
        )

    def cli_delete(root, name):
        try:
            cmd_project_delete(SimpleNamespace(project=str(root), confirm_name=name))
        except SystemExit as exc:
            return exc.code, capsys.readouterr().out
        return 0, capsys.readouterr().out

    cli, studio = _two_projects(tmp_path)
    for root in (cli, studio):
        (root / "project.json").write_text(json.dumps({"name": "Parity"}), encoding="utf-8")

    # a wrong confirmation name refuses, in the same words, and deletes nothing
    code, out = cli_delete(cli, "nope")
    body, status = studio_delete(studio, "nope")
    assert (code, status) == (1, 400) and body["error"] in out
    assert cli.exists() and studio.exists()

    # a folder that is not a project is refused the same way
    plain = tmp_path / "plain"
    plain.mkdir()
    code, out = cli_delete(plain, "plain")
    body, status = studio_delete(plain, "plain")
    assert (code, status) == (1, 400) and body["error"] in out and plain.exists()

    # the right name deletes
    code, out = cli_delete(cli, "Parity")
    body, status = studio_delete(studio, "Parity")
    assert code == 0 and status == 200 and body["success"]
    assert not cli.exists() and not studio.exists()


def _git_view(root: Path) -> dict:
    """What DataLad leaves behind that matters: the files it tracks and the commit messages (not hashes or dates)."""

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout

    def text(p):  # the dataset id is a fresh UUID per dataset
        return "".join(l for l in (root / p).read_text(encoding="utf-8").splitlines(True) if not l.strip().startswith("id = "))

    files = {p: text(p) for p in git("ls-files").splitlines() if (root / p).is_file() and not (root / p).is_symlink()}
    return {"files": files, "messages": git("log", "--format=%s").splitlines()}


def _studio_datalad(route, root, monkeypatch, body):
    import src.web.blueprints.projects as projects_routes
    from flask import Flask

    monkeypatch.setattr(projects_routes, "get_current_project", lambda: {"path": str(root)})
    with Flask(__name__).test_request_context(method="POST", json=body):
        response = getattr(projects_routes, route)()
    response, status = (response, 200) if not isinstance(response, tuple) else response
    return response.get_json(), status


@pytest.mark.skipif(not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex")
@pytest.mark.slow
def test_enabling_and_saving_datalad_do_the_same_in_the_cli_and_in_studio(tmp_path, monkeypatch, capsys):
    from src.cli.commands.datalad import cmd_datalad_enable, cmd_datalad_save

    cli, studio = _two_projects(tmp_path)

    # enabling needs the confirmation in both
    with pytest.raises(SystemExit) as refused:
        cmd_datalad_enable(SimpleNamespace(project=str(cli), message=None, yes=False, json=True))
    body, status = _studio_datalad("enable_datalad_for_project", studio, monkeypatch, {})
    assert refused.value.code == 2 and status == 400 and body["error"] in capsys.readouterr().out

    cmd_datalad_enable(SimpleNamespace(project=str(cli), message=None, yes=True, json=True))
    body, status = _studio_datalad("enable_datalad_for_project", studio, monkeypatch, {"confirmed": True})
    assert status == 200 and body["success"] and json.loads(capsys.readouterr().out)["success"]
    assert _git_view(cli) == _git_view(studio)

    # saving a change commits it with the same default message
    for root in (cli, studio):
        (root / "notes.txt").write_text("a change", encoding="utf-8")
    cmd_datalad_save(SimpleNamespace(project=str(cli), message=None, json=True))
    body, status = _studio_datalad("save_datalad_snapshot", studio, monkeypatch, {})
    assert status == 200 and body["success"] and json.loads(capsys.readouterr().out)["success"]
    assert _git_view(cli) == _git_view(studio)
    assert "Save PRISM project changes" in _git_view(cli)["messages"]
