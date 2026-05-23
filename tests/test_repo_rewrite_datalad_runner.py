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
