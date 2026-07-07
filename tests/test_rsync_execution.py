from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.rsync_execution import (
    ensure_remote_directory,
    is_remote_target,
    run_rsync_push,
    run_rsync_verify,
)


class _FakeRsyncPopen:
    """Minimal stand-in for subprocess.Popen's streaming contract used by
    run_rsync_push (`.stdout` iterable, `.wait()`, `.returncode`,
    `.terminate()`), without spawning a real rsync process."""

    def __init__(self, returncode: int = 0, stdout_lines: "list[str] | None" = None):
        self.returncode = returncode
        self.stdout = iter(stdout_lines or [])
        self.terminated = False

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        pass


# ===== is_remote_target: local-path vs [user@]host:/path disambiguation =====


@pytest.mark.parametrize(
    "target,expected",
    [
        ("user@host:/srv/backups/study1", True),
        ("host:/srv/backups", True),
        ("/local/backup/path", False),
        ("", False),
        ("C:\\Users\\researcher\\backup", False),  # Windows drive letter, not a host
        ("C:/Users/researcher/backup", False),
    ],
)
def test_is_remote_target_disambiguates_ssh_specs_from_local_paths(target, expected):
    assert is_remote_target(target) is expected


# ===== ensure_remote_directory =====


def test_ensure_remote_directory_creates_local_path_without_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _unexpected_run(*args, **kwargs):
        raise AssertionError("local targets must not shell out to ssh")

    monkeypatch.setattr("src.rsync_execution.subprocess.run", _unexpected_run)

    target_dir = tmp_path / "backups" / "study1"
    result = ensure_remote_directory(str(target_dir))

    assert result["success"] is True
    assert target_dir.is_dir()


def test_ensure_remote_directory_runs_ssh_mkdir_for_remote_target(
    monkeypatch: pytest.MonkeyPatch,
):
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(c) for c in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.rsync_execution.subprocess.run", _fake_run)
    monkeypatch.setattr("src.rsync_execution.shutil.which", lambda name: f"/usr/bin/{name}")

    result = ensure_remote_directory("researcher@host:/srv/backups/study1")

    assert result["success"] is True
    assert seen_commands[0] == [
        "/usr/bin/ssh",
        "researcher@host",
        "mkdir",
        "-p",
        "/srv/backups/study1",
    ]


def test_ensure_remote_directory_fails_without_ssh_executable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.rsync_execution.shutil.which", lambda name: None)

    result = ensure_remote_directory("researcher@host:/srv/backups/study1")

    assert result["success"] is False
    assert "ssh executable" in result["message"]


# ===== run_rsync_push =====


def test_run_rsync_push_is_additive_only_never_passes_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: this feature is documented as a growing backup, not
    a mirror. Passing --delete would make a local deletion propagate and
    destroy the researcher's only remaining copy on the backup destination."""
    seen_commands: list[list[str]] = []

    def _fake_popen(command, **kwargs):
        seen_commands.append([str(c) for c in command])
        return _FakeRsyncPopen(returncode=0, stdout_lines=[])

    monkeypatch.setattr("src.rsync_execution.subprocess.Popen", _fake_popen)

    dest = tmp_path / "dest"
    result = run_rsync_push(
        tmp_path / "source",
        remote_target=str(dest),
        rsync_executable="/usr/bin/rsync",
    )

    assert result["success"] is True
    command = seen_commands[0]
    assert "--delete" not in command
    assert "-a" in command


def test_run_rsync_push_requires_a_remote_target(tmp_path: Path):
    result = run_rsync_push(
        tmp_path, remote_target="", rsync_executable="/usr/bin/rsync"
    )

    assert result["success"] is False
    assert "No remote target" in result["message"]


def test_run_rsync_push_reports_missing_executable_without_running_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _unexpected_popen(*args, **kwargs):
        raise AssertionError("rsync should not run without a resolved executable")

    monkeypatch.setattr("src.rsync_execution.subprocess.Popen", _unexpected_popen)
    monkeypatch.setattr("src.rsync_execution.shutil.which", lambda _name: None)

    result = run_rsync_push(tmp_path, remote_target=str(tmp_path / "dest"), rsync_executable="")

    assert result["attempted"] is False
    assert result["success"] is False
    assert "rsync executable is not available" in result["message"]


def test_run_rsync_push_fails_on_nonzero_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.rsync_execution.subprocess.Popen",
        lambda *a, **k: _FakeRsyncPopen(returncode=23, stdout_lines=["rsync: some files vanished\n"]),
    )

    result = run_rsync_push(
        tmp_path, remote_target=str(tmp_path / "dest"), rsync_executable="/usr/bin/rsync"
    )

    assert result["success"] is False
    assert "23" in result["message"]


def test_run_rsync_push_stops_and_reports_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake_process = _FakeRsyncPopen(returncode=0, stdout_lines=["sending file 1\n", "sending file 2\n"])
    monkeypatch.setattr("src.rsync_execution.subprocess.Popen", lambda *a, **k: fake_process)

    result = run_rsync_push(
        tmp_path,
        remote_target=str(tmp_path / "dest"),
        rsync_executable="/usr/bin/rsync",
        is_cancelled=lambda: True,
    )

    assert result["success"] is False
    assert "Cancelled" in result["message"]
    assert fake_process.terminated is True


# ===== run_rsync_verify: destination-matches-source truth table =====


def test_run_rsync_verify_true_when_no_lines_are_itemized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.rsync_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="sending incremental file list\n", stderr=""
        ),
    )

    result = run_rsync_verify(
        tmp_path, remote_target=str(tmp_path / "dest"), rsync_executable="/usr/bin/rsync"
    )

    assert result["verified"] is True
    assert result["mismatched_paths"] == []


def test_run_rsync_verify_false_when_itemized_changes_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.rsync_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout="sending incremental file list\n>fcst...... sub-001/anat/sub-001_T1w.nii.gz\n",
            stderr="",
        ),
    )

    result = run_rsync_verify(
        tmp_path, remote_target=str(tmp_path / "dest"), rsync_executable="/usr/bin/rsync"
    )

    assert result["verified"] is False
    assert len(result["mismatched_paths"]) == 1
    assert "sub-001_T1w.nii.gz" in result["mismatched_paths"][0]


def test_run_rsync_verify_uses_dry_run_and_checksum_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: verification must never actually transfer files
    (must stay a dry run) and must compare content, not just mtimes."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(c) for c in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.rsync_execution.subprocess.run", _fake_run)

    run_rsync_verify(
        tmp_path, remote_target=str(tmp_path / "dest"), rsync_executable="/usr/bin/rsync"
    )

    command = seen_commands[0]
    assert "-acn" in command  # archive + checksum + dry-run


def test_run_rsync_verify_fails_on_nonzero_returncode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.rsync_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="connection refused"),
    )

    result = run_rsync_verify(
        tmp_path, remote_target=str(tmp_path / "dest"), rsync_executable="/usr/bin/rsync"
    )

    assert result["success"] is False
    assert result["verified"] is False
    assert "connection refused" in result["message"]
