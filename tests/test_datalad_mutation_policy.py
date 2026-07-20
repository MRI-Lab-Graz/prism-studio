from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.datalad_mutation_policy import MutationNotFullySavedError, run_tracked_mutation
from src.datalad_project_copy import copy_files_into_project


def test_run_tracked_mutation_returns_not_tracked_for_plain_projects(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True)

    result = run_tracked_mutation(
        project_root,
        get_paths=["."],
        run_message="PRISM: noop",
        command=["echo", "noop"],
    )

    assert result.get("tracked") is False
    assert result.get("used_run") is False


def test_run_tracked_mutation_requires_datalad_in_tracked_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)

    monkeypatch.setattr(
        "src.datalad_mutation_policy.resolve_datalad_executable",
        lambda: None,
    )

    with pytest.raises(ValueError, match="require DataLad run"):
        run_tracked_mutation(
            project_root,
            get_paths=["."],
            run_message="PRISM: noop",
            command=["echo", "noop"],
        )


def _fake_subprocess_run_factory(handlers):
    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        for prefix, handler in handlers.items():
            if len(command) >= 2 and command[1] == prefix:
                return handler(command)
        raise AssertionError(f"Unexpected command: {command}")
    return _fake_run


def test_run_tracked_mutation_proceeds_once_unlock_makes_file_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    text_file = project_root / "sub-001_scans.tsv"
    text_file.write_text("filename\n")
    text_file.chmod(stat.S_IREAD)  # simulate a locked, read-only annexed file

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda cmd: "/usr/bin/datalad" if cmd == "datalad" else "",
    )

    def _unlock(command):
        text_file.chmod(stat.S_IREAD | stat.S_IWRITE)  # actually unlocks it
        return SimpleNamespace(returncode=0, stdout="unlock ok", stderr="")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory({
            "save": lambda c: SimpleNamespace(returncode=0, stdout="save ok", stderr=""),
            "get": lambda c: SimpleNamespace(returncode=0, stdout="get ok", stderr=""),
            "unlock": _unlock,
            "run": lambda c: SimpleNamespace(returncode=0, stdout="run ok", stderr=""),
        }),
    )

    result = run_tracked_mutation(
        project_root,
        get_paths=["."],
        run_message="PRISM: test",
        command=["echo", "noop"],
        content_paths=["sub-001_scans.tsv"],
    )

    assert result.get("used_run") is True
    assert result.get("unlock", {}).get("attempted") is True


def test_run_tracked_mutation_scopes_autosaves_to_mutation_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Both autosave-before-mutation calls must be scoped to this mutation's
    own paths, not the whole dataset: an unscoped `datalad save -r` re-walks
    every registered subdataset, which is ruinous when a caller (e.g.
    bids_file_deleter.py, datalad_project_copy.py) calls this once per
    subject/item over a dataset with many nested subdatasets.
    """
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    text_file = project_root / "sub-001" / "sub-001_scans.tsv"
    text_file.parent.mkdir(parents=True)
    text_file.write_text("filename\n")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda cmd: "/usr/bin/datalad" if cmd == "datalad" else "",
    )

    seen_commands: list[list[str]] = []

    def _record(command):
        seen_commands.append([str(part) for part in command])
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory({
            "save": _record,
            "get": _record,
            "unlock": _record,
            "run": _record,
        }),
    )

    run_tracked_mutation(
        project_root,
        get_paths=["sub-001"],
        run_message="PRISM: test",
        command=["echo", "noop"],
        content_paths=["sub-001/sub-001_scans.tsv"],
    )

    save_commands = [command for command in seen_commands if command[1] == "save"]
    assert len(save_commands) == 2, "Expected one pre-mutation autosave and one pre-run autosave."
    for command in save_commands:
        assert "--" in command, f"Save command was not scoped to specific paths: {command}"
        scoped_paths = command[command.index("--") + 1 :]
        assert scoped_paths, f"Save command had an empty path scope: {command}"
        assert all("sub-001" in path for path in scoped_paths)


def test_run_tracked_mutation_raises_clear_error_when_file_stays_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: `datalad unlock` is best-effort and its exit code
    can't be trusted (it's a no-op for non-annexed files), so a file that's
    still genuinely locked after unlock must be caught here with a clear,
    actionable message — not left to fail deep inside the wrapped command
    with a raw PermissionError."""
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    text_file = project_root / "sub-001_scans.tsv"
    text_file.write_text("filename\n")
    text_file.chmod(stat.S_IREAD)  # stays locked even after "unlock" below

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda cmd: "/usr/bin/datalad" if cmd == "datalad" else "",
    )

    run_was_attempted = False

    def _run(command):
        nonlocal run_was_attempted
        run_was_attempted = True
        return SimpleNamespace(returncode=0, stdout="run ok", stderr="")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory({
            "save": lambda c: SimpleNamespace(returncode=0, stdout="save ok", stderr=""),
            "get": lambda c: SimpleNamespace(returncode=0, stdout="get ok", stderr=""),
            "unlock": lambda c: SimpleNamespace(returncode=0, stdout="unlock ok (no-op)", stderr=""),
            "run": _run,
        }),
    )

    with pytest.raises(ValueError, match="still read-only"):
        run_tracked_mutation(
            project_root,
            get_paths=["."],
            run_message="PRISM: test",
            command=["echo", "noop"],
            content_paths=["sub-001_scans.tsv"],
        )

    assert run_was_attempted is False


def _init_real_git_repo(project_root: Path, real_git: str) -> None:
    """DataLad datasets are real git repos; the dirty-tree detection this
    module relies on (`git status --porcelain`) needs a real repo underneath
    to behave meaningfully, not just a bare `.datalad` marker directory.
    Commits whatever is already on disk (e.g. the `.datalad` marker) so the
    tree starts genuinely clean rather than showing it as untracked."""
    subprocess.run([real_git, "init", "-q"], cwd=project_root, check=True)
    subprocess.run([real_git, "add", "-A"], cwd=project_root, check=True)
    subprocess.run(
        [real_git, "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "--allow-empty", "-m", "init"],
        cwd=project_root, check=True,
    )


def test_run_tracked_mutation_emergency_saves_partial_run_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: `datalad run` never saves anything when the wrapped
    command errors ("no modifications will be saved" per its own docs), even
    if that command already deleted/copied/renamed files before crashing.
    run_tracked_mutation must detect and capture that partial state via an
    emergency `datalad save`, and raise a distinct, honest error instead of
    a generic failure indistinguishable from "nothing happened"."""
    real_git = shutil.which("git")
    assert real_git, "git must be installed to run this test"

    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    _init_real_git_repo(project_root, real_git)

    target_file = project_root / "sub-001" / "sub-001_task-rest_bold.nii.gz"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"nii")
    subprocess.run([real_git, "add", "-A"], cwd=project_root, check=True)
    subprocess.run(
        [real_git, "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-m", "seed"],
        cwd=project_root, check=True,
    )

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda cmd: "/usr/bin/datalad" if cmd == "datalad" else (real_git if cmd == "git" else ""),
    )

    # `monkeypatch.setattr("src.datalad_execution.subprocess.run", ...)`
    # mutates the actual shared `subprocess` module (there's no
    # module-local copy), so any plain `subprocess.run(...)` call made from
    # *inside* the fake -- including this test file's own -- would
    # recursively hit the fake again. Capture the real function first.
    real_subprocess_run = subprocess.run

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        if command and command[0] == real_git:
            # Let real `git status` run against the actual working tree so
            # the dirty-check under test observes genuine on-disk state.
            return real_subprocess_run(
                command, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout, check=False,
            )
        if len(command) >= 2 and command[1] == "run":
            # Simulate the wrapped command partially completing (deleting
            # the target file) before it crashes.
            target_file.unlink(missing_ok=True)
            return SimpleNamespace(returncode=1, stdout="", stderr="boom: crashed midway")
        if len(command) >= 2 and command[1] in {"save", "get", "unlock"}:
            return SimpleNamespace(returncode=0, stdout=f"{command[1]} ok", stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    with pytest.raises(MutationNotFullySavedError, match="INCOMPLETE"):
        run_tracked_mutation(
            project_root,
            get_paths=["sub-001"],
            run_message="PRISM: delete files",
            command=["echo", "noop"],
        )

    # The partial deletion actually happened on disk and must not be
    # reported as though nothing changed.
    assert not target_file.exists()


def test_run_tracked_mutation_raises_plain_error_when_run_fails_with_no_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A `datalad run` failure that truly touched nothing (e.g. the wrapped
    command errored before writing anything) must not be misreported as a
    dirty, partially-applied mutation."""
    real_git = shutil.which("git")
    assert real_git, "git must be installed to run this test"

    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    _init_real_git_repo(project_root, real_git)

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda cmd: "/usr/bin/datalad" if cmd == "datalad" else (real_git if cmd == "git" else ""),
    )

    # See the sibling test above: capture the real subprocess.run before
    # patching, since the patch target is the shared module, not a
    # module-local copy.
    real_subprocess_run = subprocess.run

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        if command and command[0] == real_git:
            return real_subprocess_run(
                command, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout, check=False,
            )
        if len(command) >= 2 and command[1] == "run":
            return SimpleNamespace(returncode=1, stdout="", stderr="command not found")
        if len(command) >= 2 and command[1] in {"save", "get", "unlock"}:
            return SimpleNamespace(returncode=0, stdout=f"{command[1]} ok", stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    with pytest.raises(ValueError) as exc_info:
        run_tracked_mutation(
            project_root,
            get_paths=["."],
            run_message="PRISM: noop",
            command=["definitely-not-a-real-command"],
        )

    assert not isinstance(exc_info.value, MutationNotFullySavedError)


def test_copy_files_into_project_uses_direct_copy_for_plain_projects(tmp_path: Path):
    dataset_root = tmp_path / "project"
    dataset_root.mkdir(parents=True)
    source_file = tmp_path / "source.bin"
    source_file.write_bytes(b"\x00\x01\x02")
    destination_file = dataset_root / "rawdata" / "sub-001" / "func" / "file.edf"

    result = copy_files_into_project(
        dataset_root=dataset_root,
        copy_pairs=[(source_file, destination_file)],
        run_message="PRISM: copy",
    )

    assert destination_file.read_bytes() == b"\x00\x01\x02"
    assert result.get("copied_count") == 1
    assert result.get("copied_paths") == [
        "rawdata/sub-001/func/file.edf",
    ]
    assert result.get("datalad", {}).get("used_run") is False


def test_copy_files_into_project_parses_datalad_run_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dataset_root = tmp_path / "project"
    (dataset_root / ".datalad").mkdir(parents=True)
    source_file = tmp_path / "source.bin"
    source_file.write_bytes(b"abc")
    destination_file = dataset_root / "sub-001" / "func" / "sub-001_task-rest_physio.edf"

    def _fake_run_tracked_mutation(*args, **kwargs):
        return {
            "tracked": True,
            "used_run": True,
            "get": {"success": True},
            "run": {
                "message": "ok",
                "command": "datalad run ...",
                "stdout": (
                    '{"copied_count": 1, '
                    '"copied_paths": ["sub-001/func/sub-001_task-rest_physio.edf"]}'
                ),
            },
        }

    monkeypatch.setattr(
        "src.datalad_project_copy.run_tracked_mutation",
        _fake_run_tracked_mutation,
    )

    result = copy_files_into_project(
        dataset_root=dataset_root,
        copy_pairs=[(source_file, destination_file)],
        run_message="PRISM: copy",
    )

    assert result.get("copied_count") == 1
    assert result.get("copied_paths") == [
        "sub-001/func/sub-001_task-rest_physio.edf",
    ]
    assert result.get("datalad", {}).get("used_run") is True


def test_copy_files_into_project_runs_per_subject_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dataset_root = tmp_path / "project"
    (dataset_root / ".datalad").mkdir(parents=True)
    src_a = tmp_path / "src_a.bin"
    src_b = tmp_path / "src_b.bin"
    src_a.write_bytes(b"a")
    src_b.write_bytes(b"b")
    dst_a = dataset_root / "sub-001" / "func" / "sub-001_task-rest_physio.edf"
    dst_b = dataset_root / "sub-002" / "func" / "sub-002_task-rest_physio.edf"

    seen_messages: list[str] = []

    def _fake_run_tracked_mutation(*args, **kwargs):
        seen_messages.append(str(kwargs.get("run_message") or ""))
        if "sub-001" in str(kwargs.get("run_message") or ""):
            copied = ["sub-001/func/sub-001_task-rest_physio.edf"]
        else:
            copied = ["sub-002/func/sub-002_task-rest_physio.edf"]
        return {
            "tracked": True,
            "used_run": True,
            "get": {"success": True},
            "run": {
                "message": "ok",
                "command": "datalad run ...",
                "stdout": (
                    '{"copied_count": 1, '
                    + '"copied_paths": '
                    + json.dumps(copied)
                    + "}"
                ),
            },
        }

    monkeypatch.setattr(
        "src.datalad_project_copy.run_tracked_mutation",
        _fake_run_tracked_mutation,
    )

    result = copy_files_into_project(
        dataset_root=dataset_root,
        copy_pairs=[(src_a, dst_a), (src_b, dst_b)],
        run_message="PRISM: copy",
    )

    assert result.get("copied_count") == 2
    assert set(result.get("copied_paths") or []) == {
        "sub-001/func/sub-001_task-rest_physio.edf",
        "sub-002/func/sub-002_task-rest_physio.edf",
    }
    datalad_info = result.get("datalad") or {}
    assert datalad_info.get("run_per_subject") is True
    assert datalad_info.get("run_count") == 2
    assert any("sub-001" in message for message in seen_messages)
    assert any("sub-002" in message for message in seen_messages)
