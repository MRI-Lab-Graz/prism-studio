from __future__ import annotations

from pathlib import Path

from src.maintenance.rename_legacy_physio_filenames import (
    apply_rename_actions,
    collect_legacy_physio_renames,
)


def test_collect_legacy_physio_renames_finds_subject_and_root_sidecars(tmp_path):
    dataset_root = tmp_path / "dataset"
    physio_dir = dataset_root / "sub-001" / "ses-1" / "physio"
    physio_dir.mkdir(parents=True, exist_ok=True)

    legacy_edf = physio_dir / "sub-001_ses-1_task-rest_ecg.edf"
    legacy_json = physio_dir / "sub-001_ses-1_task-rest_ecg.json"
    root_sidecar = dataset_root / "task-rest_ecg.json"

    legacy_edf.write_bytes(b"EDF")
    legacy_json.write_text("{}", encoding="utf-8")
    root_sidecar.write_text("{}", encoding="utf-8")

    actions = collect_legacy_physio_renames(dataset_root)
    mapped = {(a.old_path.name, a.new_path.name) for a in actions}

    assert (
        "sub-001_ses-1_task-rest_ecg.edf",
        "sub-001_ses-1_task-rest_recording-ecg_physio.edf",
    ) in mapped
    assert (
        "sub-001_ses-1_task-rest_ecg.json",
        "sub-001_ses-1_task-rest_recording-ecg_physio.json",
    ) in mapped
    assert (
        "task-rest_ecg.json",
        "task-rest_recording-ecg_physio.json",
    ) in mapped


def test_apply_rename_actions_executes_rename(tmp_path):
    dataset_root = tmp_path / "dataset"
    physio_dir = dataset_root / "sub-001" / "ses-1" / "physio"
    physio_dir.mkdir(parents=True, exist_ok=True)

    legacy_edf = physio_dir / "sub-001_ses-1_task-rest_ecg.edf"
    legacy_json = physio_dir / "sub-001_ses-1_task-rest_ecg.json"
    root_sidecar = dataset_root / "task-rest_ecg.json"

    legacy_edf.write_bytes(b"EDF")
    legacy_json.write_text("{}", encoding="utf-8")
    root_sidecar.write_text("{}", encoding="utf-8")

    actions = collect_legacy_physio_renames(dataset_root)
    summary = apply_rename_actions(actions, apply=True)

    assert summary["renamed"] == 3
    assert (
        physio_dir / "sub-001_ses-1_task-rest_recording-ecg_physio.edf"
    ).exists()
    assert (
        physio_dir / "sub-001_ses-1_task-rest_recording-ecg_physio.json"
    ).exists()
    assert (dataset_root / "task-rest_recording-ecg_physio.json").exists()
    assert not legacy_edf.exists()
    assert not legacy_json.exists()
    assert not root_sidecar.exists()


def test_collect_legacy_physio_renames_skips_non_physio_task_sidecars(tmp_path):
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)

    survey_sidecar = dataset_root / "task-rest_survey.json"
    survey_sidecar.write_text("{}", encoding="utf-8")

    actions = collect_legacy_physio_renames(dataset_root)
    assert actions == []
