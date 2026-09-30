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

