from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.datalad_mutation_policy import run_tracked_mutation
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
