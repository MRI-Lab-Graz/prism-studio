from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.bids_file_deleter import BidsFileDeleter


def _touch_file(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_bids_file_deleter_apply_for_plain_project(tmp_path):
    project_root = tmp_path / "project"
    target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
    _touch_file(target)

    deleter = BidsFileDeleter(project_root)
    result = deleter.apply(modality="func", entity_filters={}, subjects=None)

    assert result["deleted_count"] == 1
    assert result["removed_empty_dirs"] >= 1
    assert "datalad" not in result
    assert "python prism.py file-management delete-files" in str(
        result.get("backend_command", "")
    )
    assert not target.exists()


def test_bids_file_deleter_apply_uses_datalad_run_dataset(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
    _touch_file(target)

    observed_commands: list[list[str]] = []

    def _fake_run(
        command,
        cwd=None,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=None,
    ):
        observed_commands.append([str(item) for item in command])
        if len(command) >= 2 and command[1] == "get":
            return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
        if len(command) >= 2 and command[1] == "run":
            payload = {
                "applied": True,
                "deleted_count": 1,
                "deleted_sidecars": 0,
                "removed_empty_dirs": 1,
                "backend_command": "python prism.py file-management delete-files --apply",
            }
            return SimpleNamespace(
                returncode=0,
                stdout=f"run log\n{json.dumps(payload)}\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "src.datalad_execution.shutil.which",
        lambda command: "/usr/bin/datalad" if command == "datalad" else "",
    )
    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    deleter = BidsFileDeleter(project_root)
    result = deleter.apply(modality="func", entity_filters={}, subjects=None)

    assert result["deleted_count"] == 1

    datalad = result.get("datalad")
    assert isinstance(datalad, dict)
    assert datalad.get("enabled") is True
    assert datalad.get("available") is True
    assert datalad.get("used_run") is True
    assert "datalad run" in str(datalad.get("command", ""))
    assert "python prism.py file-management delete-files" in str(
        result.get("backend_command", "")
    )

    assert any(command[:2] == ["/usr/bin/datalad", "get"] for command in observed_commands)
    assert any(command[:2] == ["/usr/bin/datalad", "run"] for command in observed_commands)


def test_bids_file_deleter_apply_reports_missing_datalad_executable(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
    _touch_file(target)

    monkeypatch.setattr("src.datalad_execution.shutil.which", lambda _: None)

    deleter = BidsFileDeleter(project_root)
    with pytest.raises(ValueError, match="require DataLad run"):
        deleter.apply(modality="func", entity_filters={}, subjects=None)

    # Strict mode: tracked datasets must not mutate when DataLad is unavailable.
    assert target.exists()
