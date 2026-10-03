"""prism_tools.py datalad doctor."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import src.cli.commands.datalad as cli  # noqa: E402


def _results(ok):
    return [{"name": "git", "ok": True, "detail": "v", "fix": ""},
            {"name": "datalad", "ok": ok, "detail": "", "fix": "install it"}]


def test_doctor_exits_nonzero_and_prints_fix_when_a_check_fails(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_doctor", lambda url: _results(False))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_doctor(SimpleNamespace(url=None, project=None, json=False))
    assert exc.value.code == 1
    assert "install it" in capsys.readouterr().out


def test_doctor_json_and_success_exit(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_doctor", lambda url: _results(True))
    cli.cmd_datalad_doctor(SimpleNamespace(url=None, project=None, json=True))
    assert json.loads(capsys.readouterr().out)[0]["name"] == "git"


def test_doctor_takes_server_url_from_project_config(monkeypatch, tmp_path):
    (tmp_path / ".prismrc.json").write_text(json.dumps({"riaStoreUrl": "ria+ssh://u@h/s"}))
    seen = {}
    monkeypatch.setattr(cli, "run_doctor", lambda url: seen.setdefault("url", url) and _results(True))
    cli.cmd_datalad_doctor(SimpleNamespace(url=None, project=str(tmp_path), json=True))
    assert seen["url"] == "ria+ssh://u@h/s"



# --- sync / finalize -------------------------------------------------------

from src.cli.parser import build_prism_tools_parsers  # noqa: E402


class FakeManager:
    """Stands in for ProjectManager; records the call and returns a canned result."""

    def __init__(self, result, raises=None):
        self.result, self.raises, self.calls = result, raises, []

    def _call(self, name, project, **kw):
        self.calls.append((name, str(project), kw))
        if self.raises:
            raise self.raises
        cb = kw.get("progress_callback")
        if cb:
            cb(40, "Syncing dataset to server...")
        return self.result

    def sync_project_to_ria(self, project, **kw):
        return self._call("sync", project, **kw)

    def finalize_project_upload(self, project, **kw):
        return self._call("finalize", project, **kw)


def _args(**kw):
    base = dict(project="/p", url=None, sibling_name=None, alias=None, verify=False,
                verify_mode="fast", mark_annex_dead=False, yes=False, json=False)
    return SimpleNamespace(**{**base, **kw})


def test_sync_passes_options_through_prints_progress_and_succeeds(monkeypatch, capsys):
    mgr = FakeManager({"success": True, "message": "Synced to server."})
    monkeypatch.setattr(cli, "_manager", lambda: mgr)

    cli.cmd_datalad_sync(_args(url="ria+ssh://u@h/s", sibling_name="lab", alias="st", verify=True))

    name, project, kw = mgr.calls[0]
    assert (name, project) == ("sync", "/p")
    assert (kw["ria_url"], kw["sibling_name"], kw["alias"], kw["verify"]) == ("ria+ssh://u@h/s", "lab", "st", True)
    out = capsys.readouterr().out
    assert "40%" in out and "Syncing dataset to server..." in out and "Synced to server." in out


def test_sync_failure_prints_the_message_and_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_manager", lambda: FakeManager({"success": False, "message": "Cannot reach the server."}))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_sync(_args())
    assert exc.value.code == 1
    assert "Cannot reach the server." in capsys.readouterr().out


def test_sync_without_a_configured_server_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_manager", lambda: FakeManager(None, raises=ValueError("No DataLad server URL configured.")))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_sync(_args())
    assert exc.value.code == 2
    assert "No DataLad server URL configured." in capsys.readouterr().out


def test_sync_json_emits_the_result_without_progress_lines(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_manager", lambda: FakeManager({"success": True, "message": "ok"}))
    cli.cmd_datalad_sync(_args(json=True))
    assert json.loads(capsys.readouterr().out) == {"success": True, "message": "ok"}


def test_finalize_refuses_to_disconnect_without_yes(monkeypatch, capsys):
    mgr = FakeManager({"success": True, "message": "done"})
    monkeypatch.setattr(cli, "_manager", lambda: mgr)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_finalize(_args())
    assert exc.value.code == 2
    assert mgr.calls == []
    assert "--yes" in capsys.readouterr().out


def test_finalize_with_yes_runs_with_its_options(monkeypatch, capsys):
    mgr = FakeManager({"success": True, "message": "Finalized."})
    monkeypatch.setattr(cli, "_manager", lambda: mgr)
    cli.cmd_datalad_finalize(_args(yes=True, verify_mode="full", mark_annex_dead=True))
    name, _, kw = mgr.calls[0]
    assert name == "finalize" and kw["verify_mode"] == "full" and kw["mark_annex_dead"] is True
    assert "Finalized." in capsys.readouterr().out


def test_finalize_failure_exits_1(monkeypatch):
    monkeypatch.setattr(cli, "_manager", lambda: FakeManager({"success": False, "message": "missing content"}))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_finalize(_args(yes=True))
    assert exc.value.code == 1


def test_parser_accepts_the_sync_and_finalize_options():
    parser, _ = build_prism_tools_parsers(ROOT)
    a = parser.parse_args(["datalad", "sync", "--project", "/p", "--url", "u@h:/x", "--verify", "--sibling-name", "lab"])
    assert (a.command, a.action, a.verify, a.sibling_name) == ("datalad", "sync", True, "lab")
    b = parser.parse_args(["datalad", "finalize", "--project", "/p", "--verify-mode", "full", "--mark-annex-dead", "--yes"])
    assert (b.action, b.verify_mode, b.mark_annex_dead, b.yes) == ("finalize", "full", True, True)
