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

class FakeStatusManager:
    def __init__(self, result):
        self.result = result

    def check_datalad_clean_status(self, project):
        return self.result


def test_status_prints_the_message_and_exits_zero_with_changes_pending(monkeypatch, capsys):
    mgr = FakeStatusManager({"checked": True, "clean": False, "dirty_count": 3, "message": "3 uncommitted change(s) pending."})
    monkeypatch.setattr(cli, "_manager", lambda: mgr)
    cli.cmd_datalad_status(SimpleNamespace(project="/p", json=False))
    assert "3 uncommitted change(s) pending." in capsys.readouterr().out


def test_status_json_is_the_dict_the_studio_route_returns(monkeypatch, capsys):
    result = {"checked": True, "clean": True, "dirty_count": 0, "message": "Working tree is clean."}
    monkeypatch.setattr(cli, "_manager", lambda: FakeStatusManager(result))
    cli.cmd_datalad_status(SimpleNamespace(project="/p", json=True))
    assert json.loads(capsys.readouterr().out) == result


def test_parser_accepts_datalad_status():
    parser, _ = build_prism_tools_parsers(ROOT)
    a = parser.parse_args(["datalad", "status", "--project", "/p", "--json"])
    assert (a.command, a.action, a.project, a.json) == ("datalad", "status", "/p", True)
