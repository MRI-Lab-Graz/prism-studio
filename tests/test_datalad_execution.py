from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.datalad_execution import (
    run_datalad_create_sibling_ria,
    run_datalad_push,
    run_datalad_push_verify,
    run_datalad_remove_sibling,
    run_datalad_run,
    run_datalad_sibling_exists,
    run_datalad_unlock,
)


def test_run_datalad_unlock_command_omits_on_failure_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: unlike `get`/`save`, `datalad unlock` doesn't accept
    `--on-failure` — passing it makes argparse reject the whole command and
    print usage text instead of unlocking anything, so every file silently
    stayed locked."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="unlock ok", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_unlock(
        tmp_path,
        paths=["sub-001/sub-001_scans.tsv"],
        datalad_executable="/usr/bin/datalad",
    )

    assert result.get("success") is True
    assert len(seen_commands) == 1
    command = seen_commands[0]
    assert "--on-failure" not in command
    assert command == ["/usr/bin/datalad", "unlock", "sub-001/sub-001_scans.tsv"]


def test_run_datalad_run_escapes_literal_curly_braces_in_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: `datalad run` treats the command after `--` as a
    template supporting placeholders like {inputs}/{outputs}. A Python dict
    literal embedded in a -c script (e.g. `explicit_mapping={'sub-004': ...}`)
    contains raw curly braces that DataLad's templating then tries to parse
    as a placeholder, failing with 'unrecognized placeholder' before
    anything even runs. Literal braces must be escaped by doubling, exactly
    like Python's str.format()."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="run ok", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    script_with_dict_literal = "result={'sub-134004': 'sub-004'}"
    result = run_datalad_run(
        tmp_path,
        message="PRISM: test",
        command=["python3", "-c", script_with_dict_literal],
        datalad_executable="/usr/bin/datalad",
    )

    assert result.get("success") is True
    command = seen_commands[0]
    script_arg = command[-1]
    assert script_arg == "result={{'sub-134004': 'sub-004'}}"
    # Sanity check: doubled braces collapse back to the original literal
    # text under str.format()-style substitution, same as DataLad's own
    # template engine would do once it recognizes there's no placeholder.
    assert script_arg.format() == script_with_dict_literal


# ===== A1: RIA push/pull command construction and missing-executable guards =====
#
# These pin the exact commands the "Push to DataLad Server" feature shells
# out to, and the shared "no datalad executable" early-return contract every
# RIA function follows. See A2 below for the verification truth table that
# gates whether it's ever safe to disconnect a sibling.


def test_run_datalad_sibling_exists_detects_sibling_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="ria-store(git)\n", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_sibling_exists(
        tmp_path, sibling_name="ria-store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is True
    assert result["exists"] is True
    assert seen_commands[0] == ["/usr/bin/datalad", "siblings", "-s", "ria-store"]


def test_run_datalad_sibling_exists_false_when_name_absent_from_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="some-other-sibling(git)\n", stderr=""),
    )

    result = run_datalad_sibling_exists(
        tmp_path, sibling_name="ria-store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is True
    assert result["exists"] is False


def test_run_datalad_create_sibling_ria_requires_url(tmp_path: Path):
    result = run_datalad_create_sibling_ria(
        tmp_path, ria_url="", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False
    assert result["attempted"] is False
    assert "No RIA store URL" in result["message"]


def test_run_datalad_create_sibling_ria_builds_reconfigure_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Sibling creation must be idempotent (--existing reconfigure) so 'Sync
    now' can be clicked repeatedly throughout an ongoing study without
    erroring on an already-connected sibling."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_create_sibling_ria(
        tmp_path,
        ria_url="ria+ssh://user@host/path/to/store",
        sibling_name="ria-store",
        alias="my-study",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True
    command = seen_commands[0]
    assert command[0:3] == ["/usr/bin/datalad", "create-sibling-ria", "ria+ssh://user@host/path/to/store"]
    assert "--existing" in command
    assert command[command.index("--existing") + 1] == "reconfigure"
    assert "--new-store-ok" in command
    assert "-r" in command
    assert "--alias" in command
    assert command[command.index("--alias") + 1] == "my-study"


def test_run_datalad_create_sibling_ria_reports_failure_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="", stderr="ssh: connect to host failed"
        ),
    )

    result = run_datalad_create_sibling_ria(
        tmp_path, ria_url="ria+ssh://user@host/store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False
    assert "ssh: connect to host failed" in result["message"]


def test_run_datalad_push_uses_sibling_name_and_recursive_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="publish ok", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_push(
        tmp_path, sibling_name="ria-store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is True
    command = seen_commands[0]
    assert command[0:2] == ["/usr/bin/datalad", "push"]
    assert "--to" in command
    assert command[command.index("--to") + 1] == "ria-store"
    assert "-r" in command


def test_run_datalad_push_fails_on_nonzero_returncode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="connection refused"),
    )

    result = run_datalad_push(
        tmp_path, sibling_name="ria-store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False
    assert "connection refused" in result["message"]


def test_run_datalad_push_fails_on_embedded_failure_marker_despite_zero_returncode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: `datalad push` can exit 0 while still reporting
    per-path failures in its own output (e.g. a partial multi-dataset push).
    Trusting only the return code would report success on a partially failed
    push, which is exactly the failure mode run_datalad_push_verify (A2)
    exists to catch independently -- but push itself must not paper over it
    either."""
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout="publish(ok): sub-001 (dataset)\npublish(failed): sub-002/anat/sub-002_T1w.nii.gz (file)",
            stderr="",
        ),
    )

    result = run_datalad_push(
        tmp_path, sibling_name="ria-store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False


def test_run_datalad_remove_sibling_removes_both_git_and_storage_remotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A RIA sibling is a pair (`<name>` git remote + `<name>-storage` ORA
    special remote); both must be removed or the local clone still has a
    live connection to the archive after 'Finalize & disconnect'."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_remove_sibling(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True
    removed_sibling_args = [cmd[-1] for cmd in seen_commands if "siblings" in cmd]
    assert "ria-store" in removed_sibling_args
    assert "ria-store-storage" in removed_sibling_args


def test_run_datalad_remove_sibling_fails_if_any_dataset_root_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    other_root = tmp_path / "sub-dataset"
    other_root.mkdir()

    def _fake_run(command, cwd=None, **kwargs):
        # Fail every command for the second dataset root, including the
        # `git remote remove` fallback, so it can't be masked by the retry.
        if str(cwd) == str(other_root):
            return SimpleNamespace(returncode=1, stdout="", stderr="fatal: no such remote")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_remove_sibling(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path, other_root],
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is False
    assert str(other_root) in result["message"]


@pytest.mark.parametrize(
    "func,kwargs",
    [
        (run_datalad_sibling_exists, {}),
        (run_datalad_create_sibling_ria, {"ria_url": "ria+ssh://user@host/store"}),
        (run_datalad_push, {}),
        (
            run_datalad_remove_sibling,
            {"dataset_roots": []},
        ),
    ],
)
def test_ria_functions_report_missing_datalad_executable_without_running_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, func, kwargs
):
    """Every RIA function must fail closed (never attempt a command) when no
    datalad executable is resolvable, rather than crashing on a subprocess
    call with an empty command list."""

    def _unexpected_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called without a datalad executable")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _unexpected_run)
    monkeypatch.setattr("src.datalad_execution.shutil.which", lambda _name: None)

    result = func(tmp_path, datalad_executable="", **kwargs)

    assert result["success"] is False
    assert "DataLad executable is not available" in result["message"]


# ===== A2: run_datalad_push_verify -- the disconnect-gating truth table =====
#
# `finalize_project_upload` only removes the local sibling when this
# function's `verified` flag is True. Getting any of these cases wrong means
# the app could tell a scientist their data is safely archived and disconnect
# when it isn't.


def test_push_verify_true_when_no_annexed_content_is_outstanding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    result = run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="/usr/bin/datalad",
    )

    assert result["verified"] is True
    assert result["success"] is True
    assert result["unverified_paths"] == []


def test_push_verify_uses_storage_sibling_name_not_git_sibling_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`git annex find --not --in` needs a remote UUID git-annex can resolve,
    which only the `-storage` half of the RIA sibling pair has -- checking
    against the plain git remote name would either error or silently check
    the wrong thing."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="/usr/bin/datalad",
    )

    command = seen_commands[0]
    assert command[-1] == "ria-store-storage"
    assert "--not" in command and "--in" in command


def test_push_verify_false_when_a_file_is_outstanding_on_the_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="sub-001/anat/sub-001_T1w.nii.gz\n", stderr=""
        ),
    )

    result = run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="/usr/bin/datalad",
    )

    assert result["verified"] is False
    assert result["success"] is True  # the check itself completed
    assert len(result["unverified_paths"]) == 1
    assert "sub-001_T1w.nii.gz" in result["unverified_paths"][0]


def test_push_verify_false_and_unchecked_when_annex_find_itself_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A failed check is not the same as a confirmed-missing file: both must
    block disconnect, but they're reported differently so the failure isn't
    misread as 'nothing missing'."""
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="", stderr="git-annex: not a git-annex repository"
        ),
    )

    result = run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="/usr/bin/datalad",
    )

    assert result["verified"] is False
    assert result["success"] is False
    assert "could not complete" in result["message"].lower()


def test_push_verify_checks_every_dataset_root_and_aggregates_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A multi-dataset (derivatives/recipes subdataset) push must not report
    verified just because the *first* dataset root came back clean."""
    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    dirty_root = tmp_path / "dirty"
    dirty_root.mkdir()

    def _fake_run(command, cwd=None, **kwargs):
        if str(cwd) == str(dirty_root):
            return SimpleNamespace(returncode=0, stdout="derivatives/pipeline/out.nii.gz\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[clean_root, dirty_root],
        datalad_executable="/usr/bin/datalad",
    )

    assert result["verified"] is False
    assert len(result["per_dataset"]) == 2
    assert any("out.nii.gz" in path for path in result["unverified_paths"])


def test_push_verify_false_when_annex_find_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import subprocess as _subprocess

    def _raise_timeout(command, **kwargs):
        raise _subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _raise_timeout)

    result = run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="/usr/bin/datalad",
        timeout_seconds=5,
    )

    assert result["verified"] is False
    assert result["success"] is False


def test_push_verify_reports_missing_executable_without_marking_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _unexpected_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called without a datalad executable")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _unexpected_run)
    monkeypatch.setattr("src.datalad_execution.shutil.which", lambda _name: None)

    result = run_datalad_push_verify(
        tmp_path,
        sibling_name="ria-store",
        dataset_roots=[tmp_path],
        datalad_executable="",
    )

    assert result["attempted"] is False
    assert result["verified"] is False
    assert result["success"] is False
