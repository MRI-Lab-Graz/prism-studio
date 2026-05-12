from __future__ import annotations

from pathlib import Path
import sys

from src.maintenance.rename_legacy_physio_filenames import (
    _build_parser,
    _is_physio_label,
    _iter_subject_physio_dirs,
    _split_ext,
    RenameAction,
    apply_rename_actions,
    collect_legacy_physio_renames,
    main,
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


def test_split_ext_supports_compound_and_regular_extensions():
    stem, ext = _split_ext("recording.tsv.gz")
    assert stem == "recording"
    assert ext == ".tsv.gz"

    stem_simple, ext_simple = _split_ext("recording.edf")
    assert stem_simple == "recording"
    assert ext_simple == ".edf"


def test_iter_subject_physio_dirs_yields_direct_and_session_physio(tmp_path):
    dataset_root = tmp_path / "dataset"
    direct = dataset_root / "sub-001" / "physio"
    session = dataset_root / "sub-001" / "ses-01" / "physio"
    direct.mkdir(parents=True)
    session.mkdir(parents=True)

    paths = list(_iter_subject_physio_dirs(dataset_root))
    assert direct in paths
    assert session in paths


def test_is_physio_label_filters_known_non_physio_suffixes():
    assert _is_physio_label("ecg") is True
    assert _is_physio_label("survey") is False


def test_collect_legacy_physio_renames_skips_already_canonical_and_non_data(tmp_path):
    dataset_root = tmp_path / "dataset"
    physio_dir = dataset_root / "sub-001" / "ses-1" / "physio"
    physio_dir.mkdir(parents=True, exist_ok=True)

    (physio_dir / "sub-001_ses-1_task-rest_recording-ecg_physio.edf").write_bytes(b"EDF")
    (physio_dir / "sub-001_ses-1_task-rest_survey.edf").write_bytes(b"EDF")
    (physio_dir / "sub-001_ses-1_task-rest_ecg.json").write_text("{}", encoding="utf-8")
    (physio_dir / "notes.txt").write_text("not a data file", encoding="utf-8")

    actions = collect_legacy_physio_renames(dataset_root)
    assert actions == []


def test_apply_rename_actions_dry_run_counts_planned_and_skips_existing(tmp_path):
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)
    source = dataset_root / "task-rest_ecg.json"
    source.write_text("{}", encoding="utf-8")

    planned_target = dataset_root / "task-rest_recording-ecg_physio.json"
    actions = [
        RenameAction(old_path=source, new_path=planned_target, reason="legacy-root-sidecar"),
    ]
    summary = apply_rename_actions(actions, apply=False)
    assert summary == {"renamed": 0, "skipped_existing": 0, "planned": 1}

    planned_target.write_text("{}", encoding="utf-8")
    summary_existing = apply_rename_actions(actions, apply=False)
    assert summary_existing == {"renamed": 0, "skipped_existing": 1, "planned": 0}


def test_build_parser_supports_apply_flag():
    parser = _build_parser()
    args = parser.parse_args(["/tmp/dataset", "--apply"])
    assert args.dataset_root == "/tmp/dataset"
    assert args.apply is True


def test_main_returns_error_for_missing_dataset(monkeypatch, capsys, tmp_path):
    missing_root = tmp_path / "missing"
    monkeypatch.setattr(sys, "argv", ["rename_legacy_physio_filenames.py", str(missing_root)])

    exit_code = main()
    assert exit_code == 1
    assert "does not exist" in capsys.readouterr().out


def test_main_dry_run_reports_actions(monkeypatch, capsys, tmp_path):
    dataset_root = tmp_path / "dataset"
    physio_dir = dataset_root / "sub-001" / "ses-1" / "physio"
    physio_dir.mkdir(parents=True, exist_ok=True)
    (physio_dir / "sub-001_ses-1_task-rest_ecg.edf").write_bytes(b"EDF")
    (dataset_root / "task-rest_ecg.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["rename_legacy_physio_filenames.py", str(dataset_root)])
    exit_code = main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[DRY-RUN]" in output
    assert "Planned renames:" in output


def test_main_apply_reports_applied_renames(monkeypatch, capsys, tmp_path):
    dataset_root = tmp_path / "dataset"
    physio_dir = dataset_root / "sub-001" / "ses-1" / "physio"
    physio_dir.mkdir(parents=True, exist_ok=True)
    (physio_dir / "sub-001_ses-1_task-rest_ecg.edf").write_bytes(b"EDF")

    monkeypatch.setattr(
        sys,
        "argv",
        ["rename_legacy_physio_filenames.py", str(dataset_root), "--apply"],
    )
    exit_code = main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[APPLY]" in output
    assert "Applied renames:" in output
