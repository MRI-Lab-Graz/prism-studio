import sys
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

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
