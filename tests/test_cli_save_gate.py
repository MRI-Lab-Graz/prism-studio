# tests/test_cli_save_gate.py
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.save_gate as cmd  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402
from src.save_gate import SaveCheck  # noqa: E402


def args(**kw):
    base = dict(project="/p", check=False, install_hooks=False, status=False, json=True)
    base.update(kw)
    return SimpleNamespace(**base)


def run(capsys, **kw):
    with pytest.raises(SystemExit) as info:
        cmd.cmd_save_gate(args(**kw))
    return info.value.code, capsys.readouterr()


def test_parser_contract_used_by_the_hook():
    parser, _ = build_prism_tools_parsers(APP_ROOT)
    ns = parser.parse_args(["save-gate", "--check", "--project", "/p"])
    assert (ns.command, ns.check, ns.project, ns.install_hooks, ns.status) == ("save-gate", True, "/p", False, False)


def test_check_allowed_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(True, [], "valid"))
    monkeypatch.setattr(cmd, "audit_save", lambda *a, **k: None)
    code, out = run(capsys, check=True)
    assert code == 0 and json.loads(out.out)["allowed"] is True


def test_check_refused_exit_1_and_text_names_the_gate(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(False, [f"E{i}" for i in range(30)], "validation_errors"))
    monkeypatch.setattr(cmd, "audit_save", lambda *a, **k: None)
    code, out = run(capsys, check=True, json=False)
    assert code == 1
    assert out.out.startswith("PRISM save gate: 30 validation error(s). Fix them, then save.")
    assert out.out.count("  - E") == 20


def test_check_audits_every_decision(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(False, ["E"], "validation_errors"))
    monkeypatch.setattr(cmd, "audit_save", lambda root, check: seen.append((str(root), check.allowed)))
    run(capsys, check=True)
    assert seen == [("/p", False)]


def test_install_hooks_reports_foreign_as_exit_2(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "install_save_hooks", lambda p: {"installed": ["/p"], "foreign": ["/p/sub-001"]})
    code, out = run(capsys, install_hooks=True)
    assert code == 2 and json.loads(out.out)["foreign"] == ["/p/sub-001"]


def test_install_hooks_ok_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(cmd, "install_save_hooks", lambda p: {"installed": ["/p"], "foreign": []})
    assert run(capsys, install_hooks=True)[0] == 0


def test_status_lists_hook_per_dataset(tmp_path, monkeypatch, capsys):
    sub = tmp_path / "sub-001"
    for d in (tmp_path, sub):
        (d / ".git").mkdir(parents=True)
    monkeypatch.setattr(cmd, "_dataset_roots", lambda p: [tmp_path, sub])
    monkeypatch.setattr(cmd, "has_save_hook", lambda r: r == tmp_path)
    code, out = run(capsys, status=True)
    assert code == 0
    assert json.loads(out.out)["datasets"] == {str(tmp_path): True, str(sub): False}


@pytest.mark.parametrize("reason,code", [("validation_errors", 1), ("git_error", 2), ("validator_crash", 2)])
def test_check_refusal_exit_code_by_reason(monkeypatch, capsys, reason, code):
    monkeypatch.setattr(cmd, "check_save", lambda p: SaveCheck(False, ["E"], reason))
    monkeypatch.setattr(cmd, "audit_save", lambda *a, **k: None)
    got, out = run(capsys, check=True, json=False)
    assert got == code
    assert out.out.startswith("PRISM save gate: 1 validation error(s). Fix them, then save.")


def test_audit_save_never_raises(monkeypatch, tmp_path):
    import src.save_gate as sg

    def boom(*a, **k):
        raise RuntimeError("audit broke")

    monkeypatch.setattr(sg, "_audit", boom)
    sg.audit_save(tmp_path, SaveCheck(True, [], "valid"))


def test_audit_save_records_result(monkeypatch, tmp_path):
    import src.save_gate as sg

    seen = []
    monkeypatch.setattr(sg, "_audit", lambda root, **kw: seen.append(kw))
    sg.audit_save(tmp_path, SaveCheck(False, ["a", "b"], "validation_errors"))
    assert seen[0]["result"] == "save_refused" and seen[0]["error_count"] == 2 and seen[0]["sibling"] == ""


def test_status_on_nonexistent_path_is_exit_2(tmp_path, capsys):
    code, out = run(capsys, project=str(tmp_path / "nope"), status=True)
    assert code == 2 and json.loads(out.out)["errors"]


def test_install_hooks_on_nonexistent_path_is_exit_2(tmp_path, capsys):
    code, out = run(capsys, project=str(tmp_path / "nope"), install_hooks=True)
    assert code == 2 and json.loads(out.out)["errors"]


def test_status_on_non_git_folder_is_exit_2(tmp_path, capsys):
    code, out = run(capsys, project=str(tmp_path), status=True)
    assert code == 2 and json.loads(out.out)["errors"]


def test_no_action_is_exit_2(capsys):
    assert run(capsys)[0] == 2


def test_not_a_git_repo_is_exit_2_not_a_traceback(tmp_path, capsys):
    code, out = run(capsys, project=str(tmp_path), install_hooks=True)
    assert code == 2 and json.loads(out.out)["errors"]
