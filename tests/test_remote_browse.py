from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.remote_browse import create_remote_directory, list_remote_directory


def test_list_remote_directory_reports_missing_ssh_executable(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("src.remote_browse.shutil.which", lambda _name: None)

    result = list_remote_directory("user@host", "/srv/backups", ssh_executable="")

    assert result["success"] is False
    assert "ssh executable is not available" in result["message"]


def test_list_remote_directory_requires_a_host():
    result = list_remote_directory("", "/srv/backups", ssh_executable="/usr/bin/ssh")

    assert result["success"] is False
    assert "No host" in result["message"]


def test_list_remote_directory_parses_resolved_path_and_directories_only(
    monkeypatch: pytest.MonkeyPatch,
):
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(c) for c in command])
        stdout = "\n".join(
            [
                "/srv/backups/study1",  # resolved absolute path from `pwd`
                "derivatives/",
                "sourcedata/",
                "notes.txt",  # a plain file -- must be excluded
            ]
        )
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr("src.remote_browse.subprocess.run", _fake_run)

    result = list_remote_directory(
        "user@host", "study1", ssh_executable="/usr/bin/ssh"
    )

    assert result["success"] is True
    assert result["path"] == "/srv/backups/study1"
    assert result["parent"] == "/srv/backups"
    assert {d["name"] for d in result["dirs"]} == {"derivatives", "sourcedata"}
    assert {d["path"] for d in result["dirs"]} == {
        "/srv/backups/study1/derivatives",
        "/srv/backups/study1/sourcedata",
    }
    # The remote path is shell-quoted into a single command string, sent as
    # one argv element -- never split into separate local argv tokens.
    command = seen_commands[0]
    assert command[0] == "/usr/bin/ssh"
    assert command[1] == "user@host"
    assert "study1" in command[2]


def test_list_remote_directory_reports_root_as_having_no_parent(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "src.remote_browse.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="/\nsrv/", stderr=""),
    )

    result = list_remote_directory("user@host", "/", ssh_executable="/usr/bin/ssh")

    assert result["success"] is True
    assert result["path"] == "/"
    assert result["parent"] is None


def test_list_remote_directory_fails_when_path_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "src.remote_browse.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="", stderr="bash: line 1: cd: /no/such/dir: No such file or directory"
        ),
    )

    result = list_remote_directory("user@host", "/no/such/dir", ssh_executable="/usr/bin/ssh")

    assert result["success"] is False
    assert "No such file or directory" in result["message"]


def test_list_remote_directory_times_out(monkeypatch: pytest.MonkeyPatch):
    import subprocess as _subprocess

    def _raise_timeout(command, **kwargs):
        raise _subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr("src.remote_browse.subprocess.run", _raise_timeout)

    result = list_remote_directory(
        "user@host", "/srv", ssh_executable="/usr/bin/ssh", timeout_seconds=5
    )

    assert result["success"] is False
    assert "timed out" in result["message"]


def test_create_remote_directory_requires_a_path():
    result = create_remote_directory("user@host", "", ssh_executable="/usr/bin/ssh")

    assert result["success"] is False
    assert "No path" in result["message"]


def test_create_remote_directory_builds_mkdir_p_and_returns_resolved_path(
    monkeypatch: pytest.MonkeyPatch,
):
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(c) for c in command])
        return SimpleNamespace(returncode=0, stdout="/srv/backups/study1/new-folder\n", stderr="")

    monkeypatch.setattr("src.remote_browse.subprocess.run", _fake_run)

    result = create_remote_directory(
        "user@host", "/srv/backups/study1/new-folder", ssh_executable="/usr/bin/ssh"
    )

    assert result["success"] is True
    assert result["path"] == "/srv/backups/study1/new-folder"
    command = seen_commands[0][2]
    assert "mkdir -p" in command


def test_create_remote_directory_reports_failure_detail(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.remote_browse.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="", stderr="mkdir: cannot create directory: Permission denied"
        ),
    )

    result = create_remote_directory(
        "user@host", "/srv/backups/study1/new-folder", ssh_executable="/usr/bin/ssh"
    )

    assert result["success"] is False
    assert "Permission denied" in result["message"]
