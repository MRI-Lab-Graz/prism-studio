from __future__ import annotations

from types import SimpleNamespace

from src.repo_rewrite_datalad_runner import apply_entity_rewrite, apply_subject_rewrite


def _fake_subprocess_run_factory(seen_commands):
    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        command_as_text = [str(item) for item in command]
        seen_commands.append(command_as_text)
        if len(command) >= 2 and command[1] in {"save", "get", "unlock"}:
            return SimpleNamespace(returncode=0, stdout=f"{command[1]} ok", stderr="")
        raise AssertionError(f"Unexpected command: {command}")
    return _fake_run


def test_apply_subject_rewrite_uses_datalad_get_and_save_when_project_is_tracked(
    tmp_path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-1293167" / "ses-01" / "func"
    func_dir.mkdir(parents=True)
    (project_root / ".datalad").mkdir(parents=True)
    (func_dir / "sub-1293167_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory(seen_commands),
    )

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("used_run") is False
    assert result.get("datalad", {}).get("tracked") is True
    assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
    assert any(command[0:2] == ["/usr/bin/datalad", "save"] for command in seen_commands)
    assert not any(command[1] == "run" for command in seen_commands)

    # The mutation ran for real, in-process — no fake JSON payload involved.
    assert not (project_root / "sub-1293167").exists()
    assert (
        project_root / "sub-167" / "ses-01" / "func" / "sub-167_ses-01_task-rest_bold.nii.gz"
    ).exists()


def test_apply_subject_rewrite_unlocks_and_fetches_content_for_text_files(
    tmp_path,
    monkeypatch,
):
    """Files whose *content* gets rewritten (not renamed) must be fetched
    with full data and unlocked before the mutation — otherwise the
    in-place write fails with PermissionError on a locked, read-only
    annexed symlink."""
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-1293167" / "ses-01" / "func"
    func_dir.mkdir(parents=True)
    (project_root / ".datalad").mkdir(parents=True)
    (func_dir / "sub-1293167_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")
    scans_path = project_root / "sub-1293167" / "ses-01" / "sub-1293167_ses-01_scans.tsv"
    scans_path.write_text("filename\nfunc/sub-1293167_ses-01_task-rest_bold.nii.gz\n")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory(seen_commands),
    )

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    scans_rel = scans_path.relative_to(project_root).as_posix()

    unlock_commands = [command for command in seen_commands if command[1] == "unlock"]
    assert unlock_commands, "Expected a `datalad unlock` call for the rewritten text file."
    assert any(scans_rel in command for command in unlock_commands)

    get_commands = [command for command in seen_commands if command[1] == "get"]
    full_content_get_commands = [command for command in get_commands if "-n" not in command]
    assert any(scans_rel in command for command in full_content_get_commands), (
        "Expected a full-content `datalad get` (no -n) for the rewritten text file."
    )

    rewritten_scans = (
        project_root / "sub-167" / "ses-01" / "sub-167_ses-01_scans.tsv"
    ).read_text()
    assert "sub-167" in rewritten_scans
    assert "sub-1293167" not in rewritten_scans


def test_apply_entity_rewrite_uses_datalad_get_and_save_when_project_is_tracked(
    tmp_path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    func_dir.mkdir(parents=True)
    (project_root / ".datalad").mkdir(parents=True)
    (func_dir / "sub-006_ses-1_task-A_run-01_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory(seen_commands),
    )

    result = apply_entity_rewrite(
        project_root,
        modality="func",
        entity="_task",
        operation="rename",
        current_value=None,
        replacement="rest",
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("used_run") is False
    assert result.get("datalad", {}).get("tracked") is True
    assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
    assert any(command[0:2] == ["/usr/bin/datalad", "save"] for command in seen_commands)
    assert not any(command[1] == "run" for command in seen_commands)

    assert (
        func_dir / "sub-006_ses-1_task-rest_run-01_bold.nii.gz"
    ).exists()


def test_apply_subject_rewrite_runs_once_per_subject_group(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    func_a = project_root / "sub-1293001" / "ses-01" / "func"
    func_b = project_root / "sub-1293002" / "ses-01" / "func"
    func_a.mkdir(parents=True)
    func_b.mkdir(parents=True)
    (func_a / "sub-1293001_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")
    (func_b / "sub-1293002_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory(seen_commands),
    )

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("save_per_subject") is True
    assert result.get("datalad", {}).get("save_count") == 2
    save_commands = [command for command in seen_commands if command[1] == "save"]
    # One autosave-before-mutation + one save-after-mutation per subject group.
    assert len(save_commands) == 4

    assert (project_root / "sub-001" / "ses-01" / "func").exists()
    assert (project_root / "sub-002" / "ses-01" / "func").exists()


def test_apply_entity_rewrite_runs_once_per_subject_group(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    func_a = project_root / "sub-006" / "ses-1" / "func"
    func_b = project_root / "sub-007" / "ses-1" / "func"
    func_a.mkdir(parents=True)
    func_b.mkdir(parents=True)
    (func_a / "sub-006_ses-1_task-A_run-01_bold.nii.gz").write_bytes(b"nii")
    (func_b / "sub-007_ses-1_task-A_run-01_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )

    seen_commands: list[list[str]] = []
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory(seen_commands),
    )

    result = apply_entity_rewrite(
        project_root,
        modality="func",
        entity="_task",
        operation="rename",
        current_value=None,
        replacement="rest",
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("save_per_subject") is True
    assert result.get("datalad", {}).get("save_count") == 2
    save_commands = [command for command in seen_commands if command[1] == "save"]
    assert len(save_commands) == 4

    assert (func_a / "sub-006_ses-1_task-rest_run-01_bold.nii.gz").exists()
    assert (func_b / "sub-007_ses-1_task-rest_run-01_bold.nii.gz").exists()


def test_apply_subject_rewrite_handles_batch_including_the_example_subject_itself(
    tmp_path, monkeypatch
):
    """Regression guard: each subject group's mutation uses a pre-resolved
    mapping (explicit_mapping) computed once up front, not a rule re-derived
    per subject from a literal example_subject. The old per-subprocess
    design re-scanned the (mutating) filesystem for every subject, so once
    the example subject itself had already been renamed earlier in the same
    batch, every later subject failed because the literal example no longer
    existed on disk. With one up-front mapping, this can't recur — confirm
    a batch that includes the example subject's own rename still renames
    every subject correctly."""
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    example_func_dir = project_root / "sub-134003" / "ses-01" / "func"
    example_func_dir.mkdir(parents=True)
    (example_func_dir / "sub-134003_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")
    other_func_dir = project_root / "sub-134004" / "ses-01" / "func"
    other_func_dir.mkdir(parents=True)
    (other_func_dir / "sub-134004_ses-01_task-rest_bold.nii.gz").write_bytes(b"nii")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )
    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run_factory([]),
    )

    result = apply_subject_rewrite(
        project_root,
        mode="example_keep",
        example_subject="sub-134003",
        keep_fragment="003",
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert not (project_root / "sub-134003").exists()
    assert not (project_root / "sub-134004").exists()
    assert (project_root / "sub-003" / "ses-01" / "func").exists()
    assert (project_root / "sub-004" / "ses-01" / "func").exists()
