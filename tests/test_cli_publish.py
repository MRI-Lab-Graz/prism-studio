# tests/test_cli_publish.py
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.publish as pub  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


def args(**kw):
    base = dict(project="/p", sibling=None, as_identity=None, check=False, install_hook=False, json=True)
    base.update(kw)
    return SimpleNamespace(**base)


def run(monkeypatch, capsys, **kw):
    with pytest.raises(SystemExit) as info:
        pub.cmd_publish(args(**kw))
    return info.value.code, json.loads(capsys.readouterr().out)


def test_parser_accepts_publish_flags():
    parser, _ = build_prism_tools_parsers(APP_ROOT)
    ns = parser.parse_args(
        ["publish", "--project", "/p", "--as", "A <a@b.c>", "--sibling", "s", "--check", "--install-hook"]
    )
    assert (ns.command, ns.project, ns.as_identity, ns.sibling, ns.check, ns.install_hook) == (
        "publish", "/p", "A <a@b.c>", "s", True, True,
    )


def test_publish_success_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(pub, "publish_to_server", lambda *a, **k: {"success": True, "reason": "pushed", "errors": [], "message": "ok"})
    code, out = run(monkeypatch, capsys, as_identity="A <a@b.c>")
    assert code == 0 and out["reason"] == "pushed"


@pytest.mark.parametrize("reason, code", [("validation_errors", 1), ("no_identity", 2), ("no_sibling", 2)])
def test_publish_refusal_exit_codes(monkeypatch, capsys, reason, code):
    monkeypatch.setattr(pub, "publish_to_server", lambda *a, **k: {"success": False, "reason": reason, "errors": ["e"], "message": "m"})
    assert run(monkeypatch, capsys)[0] == code


def test_bad_identity_is_exit_2(monkeypatch, capsys):
    assert run(monkeypatch, capsys, as_identity="garbage")[0] == 2


def test_check_mode_uses_validate_only(monkeypatch, capsys):
    monkeypatch.setattr(pub, "check_for_hook", lambda *a, **k: ["PRISM1 bad"])
    monkeypatch.setattr(pub, "publish_to_server", lambda *a, **k: pytest.fail("must not push"))
    code, out = run(monkeypatch, capsys, check=True)
    assert code == 1 and out["errors"] == ["PRISM1 bad"]


def test_install_hook_reports_existing_hook_as_exit_2(monkeypatch, capsys):
    def boom(*a, **k):
        raise pub.HookExistsError("already there")

    monkeypatch.setattr(pub, "install_hook", boom)
    assert run(monkeypatch, capsys, install_hook=True)[0] == 2


def test_hook_argument_contract():
    parser, _ = build_prism_tools_parsers(APP_ROOT)
    ns = parser.parse_args(["publish", "--check", "--project", "/p"])
    assert ns.check is True and ns.project == "/p" and ns.install_hook is False
