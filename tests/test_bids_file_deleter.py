from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_bids_file_deleter_apply_saves_datalad_dataset(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
    _touch_file(target)

    observed: dict[str, object] = {}

    def _fake_run(command, **kwargs):
        observed["command"] = command
        observed["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout="saved", stderr="")

    monkeypatch.setattr("src.bids_file_deleter.shutil.which", lambda _: "/usr/bin/datalad")
    monkeypatch.setattr("src.bids_file_deleter.subprocess.run", _fake_run)

    deleter = BidsFileDeleter(project_root)
    result = deleter.apply(modality="func", entity_filters={}, subjects=None)

    assert result["deleted_count"] == 1
    assert not target.exists()

    datalad = result.get("datalad")
    assert isinstance(datalad, dict)
    assert datalad.get("enabled") is True
    assert datalad.get("available") is True
    assert datalad.get("saved") is True
    assert "datalad save -r --updated -m" in str(datalad.get("command", ""))
    assert "python prism.py file-management delete-files" in str(
        result.get("backend_command", "")
    )

    command = observed.get("command")
    assert isinstance(command, list)
    assert command[:2] == ["/usr/bin/datalad", "save"]
    assert "-r" in command
    assert "--updated" in command
    assert observed.get("cwd") == str(project_root)


def test_bids_file_deleter_apply_reports_missing_datalad_executable(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".datalad").mkdir(parents=True)
    target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
    _touch_file(target)

    monkeypatch.setattr("src.bids_file_deleter.shutil.which", lambda _: None)

    deleter = BidsFileDeleter(project_root)
    result = deleter.apply(modality="func", entity_filters={}, subjects=None)

    assert result["deleted_count"] == 1

    datalad = result.get("datalad")
    assert isinstance(datalad, dict)
    assert datalad.get("enabled") is True
    assert datalad.get("available") is False
    assert datalad.get("saved") is False
    assert "not available" in str(datalad.get("message", "")).lower()
    assert "datalad save -r --updated -m" in str(datalad.get("command", ""))
    assert "python prism.py file-management delete-files" in str(
        result.get("backend_command", "")
    )
