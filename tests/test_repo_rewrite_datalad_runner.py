from __future__ import annotations

import json
from types import SimpleNamespace

from src.repo_rewrite_datalad_runner import apply_entity_rewrite, apply_subject_rewrite


def test_apply_subject_rewrite_uses_datalad_run_when_project_is_tracked(
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

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        seen_commands.append([str(item) for item in command])
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            payload = {
                "applied": True,
                "mapping_count": 1,
                "directory_rename_count": 1,
                "file_rename_count": 1,
                "text_update_count": 0,
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run,
    )

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("used_run") is True
    assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
    assert any(command[0:2] == ["/usr/bin/datalad", "run"] for command in seen_commands)


def test_apply_entity_rewrite_uses_datalad_run_when_project_is_tracked(
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

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        seen_commands.append([str(item) for item in command])
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            payload = {
                "applied": True,
                "rename_count": 1,
                "text_update_count": 0,
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "src.datalad_execution.subprocess.run",
        _fake_subprocess_run,
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
    assert result.get("datalad", {}).get("used_run") is True
    assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
    assert any(command[0:2] == ["/usr/bin/datalad", "run"] for command in seen_commands)


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

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        command_as_text = [str(item) for item in command]
        seen_commands.append(command_as_text)
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            subject = "sub-1293001" if "sub-1293001" in " ".join(command_as_text) else "sub-1293002"
            payload = {
                "mode": "last3",
                "rule": None,
                "allow_many_to_one": False,
                "subjects": [subject],
                "applied": True,
                "mapping": {subject: f"sub-{subject[-3:]}"},
                "mapping_count": 1,
                "directory_rename_count": 1,
                "file_rename_count": 1,
                "text_update_count": 0,
                "directory_renames": [],
                "file_renames": [],
                "text_update_files": [],
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_subprocess_run)

    result = apply_subject_rewrite(
        project_root,
        mode="last3",
        example_subject=None,
        keep_fragment=None,
        allow_many_to_one=False,
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("run_per_subject") is True
    assert result.get("datalad", {}).get("run_count") == 2
    run_commands = [command for command in seen_commands if command[1] == "run"]
    assert len(run_commands) == 2


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

    def _fake_subprocess_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        command_as_text = [str(item) for item in command]
        seen_commands.append(command_as_text)
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            subject = "sub-006" if "sub-006" in " ".join(command_as_text) else "sub-007"
            payload = {
                "modality": "func",
                "entity": "_task",
                "current_value": "A",
                "operation": "rename",
                "replacement": "rest",
                "available_modalities": ["func"],
                "available_entities": ["_task", "_run"],
                "subjects": [subject],
                "applied": True,
                "rename_count": 1,
                "text_update_count": 0,
                "renames": [
                    {
                        "from": f"{subject}/ses-1/func/{subject}_ses-1_task-A_run-01_bold.nii.gz",
                        "to": f"{subject}/ses-1/func/{subject}_ses-1_task-rest_run-01_bold.nii.gz",
                    }
                ],
                "text_update_files": [],
                "conflicts": [],
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"datalad run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_subprocess_run)

    result = apply_entity_rewrite(
        project_root,
        modality="func",
        entity="_task",
        operation="rename",
        current_value=None,
        replacement="rest",
    )

    assert result.get("applied") is True
    assert result.get("datalad", {}).get("run_per_subject") is True
    assert result.get("datalad", {}).get("run_count") == 2
    run_commands = [command for command in seen_commands if command[1] == "run"]
    assert len(run_commands) == 2
