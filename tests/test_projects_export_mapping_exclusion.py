import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.anonymizer import create_participant_mapping
from src.web.export_project import export_project


def test_export_never_includes_participants_mapping(tmp_path):
    project_dir = tmp_path / "study"
    subject_dir = project_dir / "sub-001"
    subject_dir.mkdir(parents=True)

    participants_tsv = project_dir / "participants.tsv"
    participants_tsv.write_text(
        "participant_id\tage\nsub-001\t30\n",
        encoding="utf-8",
    )

    data_file = subject_dir / "sub-001_task-test_survey.tsv"
    data_file.write_text(
        "participant_id\tvalue\nsub-001\t1\n",
        encoding="utf-8",
    )

    output_zip = tmp_path / "export.zip"

    stats = export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=True,
        deterministic=True,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    assert stats["files_processed"] >= 2

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = archive.namelist()

    assert "participants_mapping.json" not in names
    assert all(not name.endswith("/participants_mapping.json") for name in names)


def test_export_includes_root_subject_folders_without_rawdata(tmp_path):
    project_dir = tmp_path / "study"
    subject_dir = project_dir / "sub-001"
    subject_dir.mkdir(parents=True)

    participants_tsv = project_dir / "participants.tsv"
    participants_tsv.write_text(
        "participant_id\tage\nsub-001\t30\n",
        encoding="utf-8",
    )

    data_file = subject_dir / "sub-001_task-test_survey.tsv"
    data_file.write_text(
        "participant_id\tvalue\nsub-001\t1\n",
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_root_layout.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = archive.namelist()

    assert "sub-001/sub-001_task-test_survey.tsv" in names
    assert "participants.tsv" in names


def test_export_includes_root_prism_metadata_files(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n",
        encoding="utf-8",
    )
    (project_dir / "dataset_description.json").write_text(
        '{"Name": "Demo", "BIDSVersion": "1.10.1"}\n', encoding="utf-8"
    )
    (project_dir / ".prismrc.json").write_text(
        '{"schemaVersion": "stable"}\n', encoding="utf-8"
    )
    (project_dir / "task-demo_survey.json").write_text(
        '{"Study": {"TaskName": "demo"}}\n', encoding="utf-8"
    )
    (project_dir / ".bidsignore").write_text("*.log\n", encoding="utf-8")

    output_zip = tmp_path / "export_root_metadata.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "dataset_description.json" in names
    assert ".prismrc.json" in names
    assert "task-demo_survey.json" in names
    assert ".bidsignore" in names


def test_export_anonymize_keeps_overlapping_subject_ids_distinct(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-01\t30\nsub-010\t31\n",
        encoding="utf-8",
    )

    sub01_dir = project_dir / "sub-01"
    sub01_dir.mkdir(parents=True)
    (sub01_dir / "sub-01_task-test_events.tsv").write_text(
        "participant_id\tvalue\nsub-01\t1\n",
        encoding="utf-8",
    )

    sub010_func_dir = project_dir / "sub-010" / "func"
    sub010_fmap_dir = project_dir / "sub-010" / "fmap"
    sub010_func_dir.mkdir(parents=True)
    sub010_fmap_dir.mkdir(parents=True)
    (sub010_func_dir / "sub-010_task-rest_bold.nii.gz").write_bytes(b"dummy")
    (sub010_fmap_dir / "sub-010_dir-AP_epi.json").write_text(
        json.dumps(
            {
                "IntendedFor": "bids::sub-010/func/sub-010_task-rest_bold.nii.gz",
            }
        ),
        encoding="utf-8",
    )

    expected_mapping = create_participant_mapping(
        ["sub-01", "sub-010"],
        tmp_path / "mapping.json",
        id_length=6,
        deterministic=True,
    )

    output_zip = tmp_path / "export_overlap.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=True,
        deterministic=True,
        id_length=6,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    sub01_anon = expected_mapping["sub-01"]
    sub010_anon = expected_mapping["sub-010"]
    malformed_sub010 = f"{sub01_anon}0"

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())
        participants_data = archive.read("participants.tsv").decode("utf-8")
        fmap_json = json.loads(
            archive.read(f"{sub010_anon}/fmap/{sub010_anon}_dir-AP_epi.json").decode(
                "utf-8"
            )
        )

    assert f"{sub01_anon}/{sub01_anon}_task-test_events.tsv" in names
    assert f"{sub010_anon}/func/{sub010_anon}_task-rest_bold.nii.gz" in names
    assert f"{sub010_anon}/fmap/{sub010_anon}_dir-AP_epi.json" in names
    assert all(malformed_sub010 not in name for name in names)
    assert "sub-01" not in participants_data
    assert "sub-010" not in participants_data
    assert sub01_anon in participants_data
    assert sub010_anon in participants_data
    assert (
        fmap_json["IntendedFor"]
        == f"bids::{sub010_anon}/func/{sub010_anon}_task-rest_bold.nii.gz"
    )
    assert malformed_sub010 not in fmap_json["IntendedFor"]
