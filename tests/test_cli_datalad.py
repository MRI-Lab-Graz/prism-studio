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
        cli.cmd_datalad_doctor(SimpleNamespace(url=None, json=False))
    assert exc.value.code == 1
    assert "install it" in capsys.readouterr().out


def test_doctor_json_and_success_exit(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_doctor", lambda url: _results(True))
    cli.cmd_datalad_doctor(SimpleNamespace(url=None, json=True))
    assert json.loads(capsys.readouterr().out)[0]["name"] == "git"


def test_doctor_has_no_project_option():
    parser, _ = build_prism_tools_parsers(ROOT)
    with pytest.raises(SystemExit):
        parser.parse_args(["datalad", "doctor", "--project", "/p"])


# --- sync ------------------------------------------------------------------

from src.cli.parser import build_prism_tools_parsers  # noqa: E402


def _args(**kw):
    base = dict(project="/p", sibling_name=None, as_identity=None, json=False)
    return SimpleNamespace(**{**base, **kw})


def _fake_sync(monkeypatch, result):
    calls = []

    def fake(project, **kw):
        calls.append((str(project), kw))
        return result

    monkeypatch.setattr("src.share_publish.sync_with_server", fake)
    return calls


def test_sync_runs_the_one_backend_function_and_prints_its_message(monkeypatch, capsys):
    calls = _fake_sync(monkeypatch, {"success": True, "message": "Published to the server.", "errors": []})
    cli.cmd_datalad_sync(_args(sibling_name="lab", as_identity="Ada <ada@example.org>"))
    project, kw = calls[0]
    assert project == "/p" and kw["sibling_name"] == "lab" and kw["identity"].email == "ada@example.org"
    assert "Published to the server." in capsys.readouterr().out


def test_sync_failure_lists_the_errors_and_exits_1(monkeypatch, capsys):
    _fake_sync(monkeypatch, {"success": False, "message": "2 validation error(s).", "errors": ["bad name", "no sidecar"]})
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_sync(_args())
    out = capsys.readouterr().out
    assert exc.value.code == 1 and "bad name" in out and "no sidecar" in out


def test_sync_rejects_a_malformed_identity(monkeypatch, capsys):
    _fake_sync(monkeypatch, {"success": True, "message": "", "errors": []})
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_sync(_args(as_identity="nope"))
    assert exc.value.code == 2


def test_sync_json_emits_the_result(monkeypatch, capsys):
    _fake_sync(monkeypatch, {"success": True, "message": "ok", "errors": []})
    cli.cmd_datalad_sync(_args(json=True))
    assert json.loads(capsys.readouterr().out)["message"] == "ok"


def test_parser_has_sync_and_no_finalize():
    parser, _ = build_prism_tools_parsers(ROOT)
    a = parser.parse_args(["datalad", "sync", "--project", "/p", "--sibling-name", "lab", "--as", "A <a@b.org>"])
    assert (a.command, a.action, a.sibling_name, a.as_identity) == ("datalad", "sync", "lab", "A <a@b.org>")
    with pytest.raises(SystemExit):
        parser.parse_args(["datalad", "finalize", "--project", "/p"])


# --- save: validity gate override -------------------------------------------

class FakeSaveManager:
    def __init__(self, result):
        self.result, self.kw = result, None

    def save_datalad_snapshot(self, project, **kw):
        self.kw = kw
        return self.result


@pytest.mark.parametrize("flag", [False, True])
def test_save_passes_allow_invalid_through(monkeypatch, flag):
    mgr = FakeSaveManager({"success": True, "message": "Saved."})
    monkeypatch.setattr(cli, "_manager", lambda: mgr)
    cli.cmd_datalad_save(SimpleNamespace(project="/p", message=None, json=False, allow_invalid=flag))
    assert mgr.kw["allow_invalid"] is flag


def test_save_refused_for_an_invalid_dataset_exits_1_and_names_the_override(monkeypatch, capsys):
    refused = {"success": False, "error": "2 validation error(s) ... save anyway (--allow-invalid / 'Save anyway')."}
    monkeypatch.setattr(cli, "_manager", lambda: FakeSaveManager(refused))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_datalad_save(SimpleNamespace(project="/p", message=None, json=False, allow_invalid=False))
    assert exc.value.code == 1 and "--allow-invalid" in capsys.readouterr().out


def test_parser_accepts_save_allow_invalid():
    parser, _ = build_prism_tools_parsers(ROOT)
    assert parser.parse_args(["datalad", "save", "--project", "/p", "--allow-invalid"]).allow_invalid is True
    assert parser.parse_args(["datalad", "save", "--project", "/p"]).allow_invalid is False


# --- status (pending changes) ---------------------------------------------

def test_status_prints_the_message_and_the_next_step_from_one_computation(monkeypatch, capsys):
    import src.datalad_state as mod

    calls = []

    def fake_state(project, **kwargs):
        calls.append(project)
        return {"message": "3 uncommitted change(s) pending.", "next_step": "save", "server": None, "other_servers": []}

    monkeypatch.setattr(mod, "datalad_state", fake_state)
    monkeypatch.setattr(cli, "_manager", lambda: pytest.fail("status must not run a second check"))
    cli.cmd_datalad_status(SimpleNamespace(project="/p", json=False))
    out = capsys.readouterr().out
    assert "3 uncommitted change(s) pending." in out and "Next step: save" in out and calls == ["/p"]


def test_status_names_a_server_not_called_origin_and_the_option_to_use_it(monkeypatch, capsys):
    import src.datalad_state as mod

    state = {"message": "Working tree is clean.", "next_step": "put_on_server", "server": None, "other_servers": ["ria-store"]}
    monkeypatch.setattr(mod, "datalad_state", lambda project, **kwargs: state)
    cli.cmd_datalad_status(SimpleNamespace(project="/p", json=False))
    assert "Server found as 'ria-store'. Use --sibling-name ria-store." in capsys.readouterr().out


def test_parser_accepts_datalad_status():
    parser, _ = build_prism_tools_parsers(ROOT)
    a = parser.parse_args(["datalad", "status", "--project", "/p", "--json"])
    assert (a.command, a.action, a.project, a.json) == ("datalad", "status", "/p", True)


def test_parser_status_has_the_nested_check():
    parser, _ = build_prism_tools_parsers(ROOT)
    assert parser.parse_args(["datalad", "status", "--project", "/p", "--check-nested"]).check_nested is True
    assert parser.parse_args(["datalad", "status", "--project", "/p"]).check_nested is False


def test_no_datalad_config_command():
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "datalad", "config", "--project", "/p"],
        capture_output=True, text=True,
    )
    assert res.returncode == 2 and "invalid choice" in res.stderr
