import os
import shutil
import stat
import subprocess

import pytest

import src.share_publish as sp


def run(*args, cwd, env=None, check=True):
    return subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, check=check, env=env
    )


@pytest.fixture
def repos(tmp_path):
    server = tmp_path / "server.git"
    other = tmp_path / "other.git"
    for bare in (server, other):
        run("git", "init", "-q", "--bare", str(bare), cwd=tmp_path)
    share = tmp_path / "share"
    run("git", "init", "-q", str(share), cwd=tmp_path)
    run("git", "remote", "add", "ria-store", str(server), cwd=share)
    run("git", "remote", "add", "elsewhere", str(other), cwd=share)
    (share / "f").write_text("x")
    run("git", "add", "f", cwd=share)
    run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "m", cwd=share)
    run("git", "branch", "-M", "main", cwd=share)
    return share


def fake_tool(tmp_path, exit_code):
    tool = tmp_path / f"prism_tools_{exit_code}"
    tool.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def push(share, remote, tool=None):
    env = {**os.environ}
    env.pop("PRISM_TOOLS", None)
    if tool:
        env["PRISM_TOOLS"] = str(tool)
    return run("git", "push", remote, "main", cwd=share, env=env, check=False)


def test_hook_blocks_server_push_when_check_fails(repos, tmp_path):
    sp.install_hook(repos, "ria-store")
    assert push(repos, "ria-store", fake_tool(tmp_path, 1)).returncode != 0


def test_hook_allows_server_push_when_check_passes(repos, tmp_path):
    sp.install_hook(repos, "ria-store")
    assert push(repos, "ria-store", fake_tool(tmp_path, 0)).returncode == 0


def test_hook_ignores_other_remotes(repos, tmp_path):
    sp.install_hook(repos, "ria-store")
    assert push(repos, "elsewhere", fake_tool(tmp_path, 1)).returncode == 0


def test_hook_fails_closed_when_tool_is_missing(repos):
    if shutil.which("prism_tools"):
        pytest.skip("prism_tools is on PATH")
    sp.install_hook(repos, "ria-store")
    result = push(repos, "ria-store", tool=None)
    assert result.returncode != 0 and "PRISM_TOOLS" in result.stderr


def test_install_refuses_to_overwrite_a_foreign_hook(repos):
    hook = repos / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(sp.HookExistsError):
        sp.install_hook(repos, "ria-store")
    assert "mine" in hook.read_text()


def test_install_is_idempotent_for_our_own_hook(repos):
    sp.install_hook(repos, "ria-store")
    sp.install_hook(repos, "ria-store")  # no error
    assert sp.HOOK_MARKER in (repos / ".git" / "hooks" / "pre-push").read_text()


def test_check_for_hook_audits_and_returns_errors(repos, monkeypatch):
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["PRISM1 bad"])
    assert sp.check_for_hook(repos, "ria-store") == ["PRISM1 bad"]
    assert "hook_refused" in sp.audit_path(repos).read_text()
