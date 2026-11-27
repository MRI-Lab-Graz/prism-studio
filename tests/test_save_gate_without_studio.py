"""The save gate works with the PyPI package alone: no PRISM Studio checkout, no prism_tools."""

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import src.save_gate as sg

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd, env=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, env=env)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "ds"
    run("git", "init", "-q", str(root), cwd=tmp_path)
    (root / "f").write_text("x")
    run("git", "add", "f", cwd=root)
    return root


def only_on_path(tmp_path, name, exit_code):
    """A PATH holding git, sh and one fake tool; prism_tools cannot be found on it."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for real in ("git", "sh"):
        (bindir / real).symlink_to(shutil.which(real))
    if name:
        tool = bindir / name
        tool.write_text(f'#!/bin/sh\necho "PRISM save gate: {name} $*" >&2\nexit {exit_code}\n', newline="\n")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return str(bindir)


def commit(root, path, tools=None):
    env = {**os.environ, "PATH": path}
    env.pop("PRISM_TOOLS", None)
    if tools:
        env["PRISM_TOOLS"] = tools
    return run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "m", cwd=root, env=env)


needs_symlinks = pytest.mark.skipif(sys.platform == "win32", reason="builds a PATH out of symlinks")


@needs_symlinks
def test_hook_uses_prism_validator_when_there_is_no_prism_tools(repo, tmp_path):
    sg.install_save_hook(repo)
    result = commit(repo, only_on_path(tmp_path, "prism-validator", 0))
    assert result.returncode == 0, result.stderr
    assert "prism-validator save-gate --check --project" in result.stderr


@needs_symlinks
def test_hook_refuses_what_prism_validator_refuses(repo, tmp_path):
    sg.install_save_hook(repo)
    assert commit(repo, only_on_path(tmp_path, "prism-validator", 1)).returncode != 0


@needs_symlinks
def test_stale_prism_tools_setting_falls_back_to_prism_validator(repo, tmp_path):
    sg.install_save_hook(repo)
    result = commit(repo, only_on_path(tmp_path, "prism-validator", 0), tools=str(tmp_path / "gone"))
    assert result.returncode == 0, result.stderr


@needs_symlinks
def test_without_any_tool_the_commit_is_refused_and_says_what_to_install(repo, tmp_path):
    sg.install_save_hook(repo)
    result = commit(repo, only_on_path(tmp_path, None, 0))
    assert result.returncode != 0
    assert "pip install prism-validator" in result.stderr


def validator(*args, cwd):
    env = {**os.environ, "PRISM_SKIP_VENV_CHECK": "1"}  # as the installed package does
    return run(sys.executable, str(ROOT / "app" / "prism.py"), "save-gate", *args, cwd=cwd, env=env)


def test_validator_entry_point_runs_the_save_check(repo, tmp_path):
    result = validator("--check", "--project", str(repo), "--json", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"reason": "exempt_initial"' in result.stdout


def test_validator_entry_point_refuses_what_cannot_be_checked(tmp_path):
    plain = tmp_path / "not_a_dataset"
    plain.mkdir()
    result = validator("--check", "--project", str(plain), cwd=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr


def test_validator_entry_point_requires_check(repo, tmp_path):
    """Only checking ships in the package; anything else must not look like a passed check."""
    assert validator("--project", str(repo), cwd=tmp_path).returncode == 2


def test_validator_cli_prints_the_payload_as_json(repo, capsys):
    assert sg.validator_cli(["--check", "--project", str(repo), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"allowed": True, "reason": "exempt_initial", "errors": []}


def test_validator_cli_keeps_stdout_for_the_answer(monkeypatch, capsys):
    """The validator prints progress; it must not break --json."""
    def noisy(_root):
        print("progress")
        return sg.SaveCheck(False, ["E1"], "validation_errors")

    monkeypatch.setattr(sg, "check_save", noisy)
    monkeypatch.setattr(sg, "audit_save", lambda *a: None)
    assert sg.validator_cli(["--check", "--project", "/p", "--json"]) == 1
    out = capsys.readouterr()
    assert json.loads(out.out)["errors"] == ["E1"] and "progress" in out.err
    assert sg.validator_cli(["--check", "--project", "/p"]) == 1
    assert capsys.readouterr().out.startswith("PRISM save gate: 1 validation error(s).")
