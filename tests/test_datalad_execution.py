from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.datalad_execution import (
    is_ria_url,
    run_datalad_create_sibling,
    run_datalad_create_sibling_plain,
    run_datalad_create_sibling_ria,
    run_datalad_push,
    run_datalad_push_verify,
    run_datalad_remove_sibling,
    run_datalad_run,
    run_datalad_sibling_exists,
    run_datalad_unlock,
    run_datalad_upload_to_sibling,
)


class _FakeDataladPopen:
    """Minimal subprocess.Popen stand-in for the streaming create-sibling/push
    functions' contract (`.stdout` iterable, `.wait()`, `.returncode`,
    `.kill()`), mirroring tests/test_rsync_execution.py's helper. Output is
    merged stdout+stderr (as the real command runs with
    stderr=subprocess.STDOUT), so tests provide a single `stdout_lines` list."""

    def __init__(self, returncode: int = 0, stdout_lines: "list[str] | None" = None):
        self.returncode = returncode
        self.stdout = iter(stdout_lines or [])

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        pass


def _fake_popen_capturing_commands(seen_commands, *, returncode=0, stdout_lines=None):
    """Return a subprocess.Popen side_effect that records the command it was
    invoked with (mirroring the seen_commands pattern used for subprocess.run
    fakes elsewhere in this file) and yields a _FakeDataladPopen."""

    def _side_effect(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return _FakeDataladPopen(returncode=returncode, stdout_lines=stdout_lines)

    return _side_effect


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

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        _fake_popen_capturing_commands(seen_commands),
    )

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
        "src.datalad_execution.subprocess.Popen",
        lambda *a, **k: _FakeDataladPopen(
            returncode=1, stdout_lines=["ssh: connect to host failed\n"]
        ),
    )

    result = run_datalad_create_sibling_ria(
        tmp_path, ria_url="ria+ssh://user@host/store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False
    assert "ssh: connect to host failed" in result["message"]


def test_run_datalad_create_sibling_ria_streams_output_via_line_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A recursive create-sibling-ria across 100+ nested subdatasets can run
    for minutes; line_callback must receive each output line as it's
    produced (not just a final summary), matching the terminal output
    nested-subdataset registration already provides."""
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        lambda *a, **k: _FakeDataladPopen(
            returncode=0, stdout_lines=["create-sibling-ria(ok): sub-001 \n", "create-sibling-ria(ok): sub-002 \n"]
        ),
    )
    seen_lines: list[str] = []

    result = run_datalad_create_sibling_ria(
        tmp_path,
        ria_url="ria+ssh://user@host/store",
        datalad_executable="/usr/bin/datalad",
        line_callback=seen_lines.append,
    )

    assert result["success"] is True
    assert seen_lines == ["create-sibling-ria(ok): sub-001", "create-sibling-ria(ok): sub-002"]


# ===== Plain (non-RIA) sibling support: for servers not initialized as a =====
# ===== RIA store, e.g. one only ever used for rsync backups              =====


@pytest.mark.parametrize(
    "url,expected",
    [
        ("ria+ssh://user@host/store", True),
        ("ria+file:///srv/store", True),
        ("RIA+SSH://user@host/store", True),
        ("ssh://user@host/path", False),
        ("user@host:/srv/backups/study", False),
        ("/local/backup/path", False),
        ("", False),
    ],
)
def test_is_ria_url_detects_ria_scheme_only(url, expected):
    assert is_ria_url(url) is expected


def test_run_datalad_create_sibling_plain_requires_url(tmp_path: Path):
    result = run_datalad_create_sibling_plain(
        tmp_path, remote_url="", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False
    assert result["attempted"] is False
    assert "No remote sibling URL" in result["message"]


def test_run_datalad_create_sibling_plain_builds_reconfigure_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        _fake_popen_capturing_commands(seen_commands),
    )

    result = run_datalad_create_sibling_plain(
        tmp_path,
        remote_url="user@host:/srv/backups/study",
        sibling_name="server",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True
    command = seen_commands[0]
    assert command[0:3] == ["/usr/bin/datalad", "create-sibling", "user@host:/srv/backups/study"]
    assert "--existing" in command
    assert command[command.index("--existing") + 1] == "reconfigure"
    assert "-r" in command
    # Unlike the RIA variant, a plain sibling has no `--alias`/`--new-store-ok`.
    assert "--alias" not in command
    assert "--new-store-ok" not in command


def test_run_datalad_create_sibling_plain_reports_failure_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        lambda *a, **k: _FakeDataladPopen(
            returncode=1, stdout_lines=["ssh: connect to host failed\n"]
        ),
    )

    result = run_datalad_create_sibling_plain(
        tmp_path, remote_url="user@host:/srv/backups/study", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False
    assert "ssh: connect to host failed" in result["message"]


def test_run_datalad_create_sibling_dispatches_ria_url_to_create_sibling_ria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        _fake_popen_capturing_commands(seen_commands),
    )

    result = run_datalad_create_sibling(
        tmp_path,
        remote_url="ria+ssh://user@host/store",
        sibling_name="ria-store",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True
    assert "create-sibling-ria" in seen_commands[0]


def test_run_datalad_create_sibling_dispatches_plain_url_to_create_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        _fake_popen_capturing_commands(seen_commands),
    )

    result = run_datalad_create_sibling(
        tmp_path,
        remote_url="user@host:/srv/backups/study",
        sibling_name="server",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True
    command = seen_commands[0]
    assert "create-sibling" in command
    assert "create-sibling-ria" not in command


def test_run_datalad_push_uses_sibling_name_and_recursive_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        _fake_popen_capturing_commands(seen_commands, stdout_lines=["publish ok\n"]),
    )

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
        "src.datalad_execution.subprocess.Popen",
        lambda *a, **k: _FakeDataladPopen(returncode=1, stdout_lines=["connection refused\n"]),
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
        "src.datalad_execution.subprocess.Popen",
        lambda *a, **k: _FakeDataladPopen(
            returncode=0,
            stdout_lines=[
                "publish(ok): sub-001 (dataset)\n",
                "publish(failed): sub-002/anat/sub-002_T1w.nii.gz (file)\n",
            ],
        ),
    )

    result = run_datalad_push(
        tmp_path, sibling_name="ria-store", datalad_executable="/usr/bin/datalad"
    )

    assert result["success"] is False


def test_run_datalad_push_streams_output_via_line_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.Popen",
        lambda *a, **k: _FakeDataladPopen(
            returncode=0, stdout_lines=["copy sub-001/file.nii.gz ok\n"]
        ),
    )
    seen_lines: list[str] = []

    result = run_datalad_push(
        tmp_path,
        sibling_name="ria-store",
        datalad_executable="/usr/bin/datalad",
        line_callback=seen_lines.append,
    )

    assert result["success"] is True
    assert seen_lines == ["copy sub-001/file.nii.gz ok"]


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


def test_run_datalad_remove_sibling_skips_storage_remote_for_plain_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A plain (non-RIA) sibling has no `<name>-storage` companion remote --
    only the RIA path should ever attempt to remove one."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_remove_sibling(
        tmp_path,
        sibling_name="server",
        dataset_roots=[tmp_path],
        is_ria=False,
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True
    removed_sibling_args = [cmd[-1] for cmd in seen_commands if "siblings" in cmd]
    assert removed_sibling_args == ["server"]
    assert "server-storage" not in removed_sibling_args


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


def test_push_verify_checks_plain_sibling_name_directly_when_not_ria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A plain sibling has no `-storage` companion -- annexed content is
    pushed straight to `<name>`, so that's what must be checked."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, **kwargs):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    run_datalad_push_verify(
        tmp_path,
        sibling_name="server",
        dataset_roots=[tmp_path],
        is_ria=False,
        datalad_executable="/usr/bin/datalad",
    )

    command = seen_commands[0]
    assert command[-1] == "server"


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


def test_upload_to_sibling_uses_plain_create_sibling_and_no_storage_remote_for_non_ria_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """End-to-end create -> push -> verify -> disconnect for a plain (non-RIA)
    sibling: no `create-sibling-ria`, and no `<name>-storage` companion
    remote checked or removed. create/push stream via Popen; verify/disconnect
    still use plain subprocess.run (see run_datalad_push_verify's docstring),
    so both need faking here."""
    seen_commands: list[list[str]] = []

    def _fake_popen(command, **kwargs):
        cmd = [str(c) for c in command]
        seen_commands.append(cmd)
        if "push" in cmd and "--to" in cmd:
            return _FakeDataladPopen(returncode=0, stdout_lines=["publish ok\n"])
        return _FakeDataladPopen(returncode=0, stdout_lines=[])

    def _fake_run(command, cwd=None, **kwargs):
        cmd = [str(c) for c in command]
        seen_commands.append(cmd)
        if "annex" in cmd and "find" in cmd:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if ("siblings" in cmd or "remote" in cmd) and "remove" in cmd:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_upload_to_sibling(
        tmp_path,
        dataset_roots=[tmp_path],
        remote_url="user@host:/srv/backups/study",
        sibling_name="server",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["success"] is True, result
    assert result["verified"] is True
    assert result["disconnected"] is True
    assert not any("create-sibling-ria" in cmd for cmd in seen_commands)
    assert not any("server-storage" in cmd for cmd in seen_commands)


def test_upload_to_sibling_recovers_when_push_reports_failure_but_content_is_actually_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard for a live incident (129_PK01, 2026-07-21): a
    recursive `datalad push -r` across 150+ subdatasets exited non-zero with
    a log containing nothing but successful "[INFO] Finished push of
    Dataset(...)" lines -- no error text anywhere -- while independent
    verification (`git annex find --not --in`, the same check
    run_datalad_push_verify always performs) confirmed every dataset's
    content had, in fact, reached the sibling. Trusting push's own exit code
    as the final word reported a false "Push failed"/blocked disconnect even
    though nothing was actually missing. push's raw result must not
    short-circuit the orchestration -- verify is the deciding signal."""
    seen_commands: list[list[str]] = []

    def _fake_popen(command, **kwargs):
        cmd = [str(c) for c in command]
        seen_commands.append(cmd)
        if "push" in cmd and "--to" in cmd:
            # Non-zero exit, but the log itself contains no failure marker --
            # exactly what was observed live.
            return _FakeDataladPopen(
                returncode=1,
                stdout_lines=["[INFO] Finished push of Dataset(/data/proj)\n"],
            )
        return _FakeDataladPopen(returncode=0, stdout_lines=[])

    def _fake_run(command, cwd=None, **kwargs):
        cmd = [str(c) for c in command]
        seen_commands.append(cmd)
        if "annex" in cmd and "find" in cmd:
            # Nothing missing: independent verification proves the push
            # actually succeeded despite its own non-zero exit code.
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if ("siblings" in cmd or "remote" in cmd) and "remove" in cmd:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_upload_to_sibling(
        tmp_path,
        dataset_roots=[tmp_path],
        remote_url="ria+ssh://user@host/store",
        sibling_name="ria-store",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["verified"] is True, result
    assert result["success"] is True, result
    assert result["disconnected"] is True


def test_upload_to_sibling_still_fails_when_push_fails_and_content_is_actually_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Companion to the false-failure regression guard above: when push
    fails AND independent verification also finds content genuinely missing,
    the failure must still be reported and disconnect must still be blocked."""

    def _fake_popen(command, **kwargs):
        cmd = [str(c) for c in command]
        if "push" in cmd and "--to" in cmd:
            return _FakeDataladPopen(returncode=1, stdout_lines=["connection refused\n"])
        return _FakeDataladPopen(returncode=0, stdout_lines=[])

    def _fake_run(command, cwd=None, **kwargs):
        cmd = [str(c) for c in command]
        if "annex" in cmd and "find" in cmd:
            return SimpleNamespace(returncode=0, stdout="sub-001/scan.nii.gz\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_upload_to_sibling(
        tmp_path,
        dataset_roots=[tmp_path],
        remote_url="ria+ssh://user@host/store",
        sibling_name="ria-store",
        datalad_executable="/usr/bin/datalad",
    )

    assert result["verified"] is False
    assert result["success"] is False
    assert result["disconnected"] is False
    assert "connection refused" in result["message"]
