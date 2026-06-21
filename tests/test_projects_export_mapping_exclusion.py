import json
import gzip
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

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


def test_export_can_exclude_selected_subjects(tmp_path):
    project_dir = tmp_path / "study"
    sub001_dir = project_dir / "sub-001" / "survey"
    sub002_dir = project_dir / "sub-002" / "survey"
    sub001_dir.mkdir(parents=True)
    sub002_dir.mkdir(parents=True)

    (sub001_dir / "sub-001_task-test_survey.tsv").write_text(
        "participant_id\tvalue\nsub-001\t1\n",
        encoding="utf-8",
    )
    (sub002_dir / "sub-002_task-test_survey.tsv").write_text(
        "participant_id\tvalue\nsub-002\t2\n",
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_subject_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        exclude_subjects={"sub-002"},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "sub-001/survey/sub-001_task-test_survey.tsv" in names
    assert "sub-002/survey/sub-002_task-test_survey.tsv" not in names


def test_export_defacing_uses_overlay_copy_for_datalad_free_zip(tmp_path):
    project_dir = tmp_path / "study"
    anat_dir = project_dir / "sub-001" / "ses-1" / "anat"
    anat_dir.mkdir(parents=True)
    original_nifti = anat_dir / "sub-001_ses-1_acq-mprage_T1w.nii.gz"
    original_nifti.write_bytes(b"original")
    output_zip = tmp_path / "export_defaced.zip"

    overlay_root = tmp_path / "overlay" / "study_defacing_export"
    overlay_nifti = overlay_root / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_acq-mprage_T1w.nii.gz"
    overlay_nifti.parent.mkdir(parents=True, exist_ok=True)
    overlay_nifti.write_bytes(b"defaced")

    with patch(
        "src.mri_json_scrubber.prepare_defacing_export_copy",
        return_value={"success": True, "target_path": str(overlay_root)},
    ) as mock_prepare, patch(
        "src.mri_json_scrubber.deface_anatomical_scans",
        return_value={"success": True, "counts": {"defaced": 1, "already_defaced": 0, "failed": 0}},
    ) as mock_deface:
        stats = export_project(
            project_path=project_dir,
            output_zip=output_zip,
            anonymize=False,
            include_derivatives=False,
            include_code=False,
            include_analysis=False,
            deface_anatomical_scans=True,
            defacing_selected_variants={"acq:mprage|suffix:t1w"},
            exclude_version_control_metadata=True,
        )

    with zipfile.ZipFile(output_zip, "r") as archive:
        assert archive.read("sub-001/ses-1/anat/sub-001_ses-1_acq-mprage_T1w.nii.gz") == b"defaced"

    assert stats["defacing"]["counts"]["defaced"] == 1
    _prepare_args, prepare_kwargs = mock_prepare.call_args
    assert prepare_kwargs["preserve_datalad_metadata"] is False
    deface_args, deface_kwargs = mock_deface.call_args
    assert deface_args[0] == overlay_root.resolve(strict=False)
    assert deface_kwargs["selected_variants"] == {"acq:mprage|suffix:t1w"}


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


def test_export_can_exclude_survey_tasks_and_matching_root_sidecars(tmp_path):
    project_dir = tmp_path / "study"
    survey_dir = project_dir / "sub-001" / "ses-01" / "survey"
    survey_dir.mkdir(parents=True)

    (project_dir / "task-ads_survey.json").write_text(
        '{"Study": {"TaskName": "ads"}}\n', encoding="utf-8"
    )
    (project_dir / "task-phq_survey.json").write_text(
        '{"Study": {"TaskName": "phq"}}\n', encoding="utf-8"
    )
    (survey_dir / "sub-001_ses-01_task-ads_survey.tsv").write_text(
        "participant_id\tvalue\nsub-001\t1\n",
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-01_task-ads_survey.json").write_text(
        '{"Study": {"TaskName": "ads"}}\n', encoding="utf-8"
    )
    (survey_dir / "sub-001_ses-01_task-phq_survey.tsv").write_text(
        "participant_id\tvalue\nsub-001\t2\n",
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-01_task-phq_survey.json").write_text(
        '{"Study": {"TaskName": "phq"}}\n', encoding="utf-8"
    )

    output_zip = tmp_path / "export_survey_task_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        exclude_tasks={"survey": {"ads"}},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "sub-001/ses-01/survey/sub-001_ses-01_task-ads_survey.tsv" not in names
    assert "sub-001/ses-01/survey/sub-001_ses-01_task-ads_survey.json" not in names
    assert "task-ads_survey.json" not in names
    assert "sub-001/ses-01/survey/sub-001_ses-01_task-phq_survey.tsv" in names
    assert "sub-001/ses-01/survey/sub-001_ses-01_task-phq_survey.json" in names
    assert "task-phq_survey.json" in names


def test_export_can_exclude_complex_survey_tasks_and_matching_root_sidecars(tmp_path):
    project_dir = tmp_path / "study"
    survey_dir = project_dir / "sub-001" / "ses-01" / "survey"
    survey_dir.mkdir(parents=True)

    (project_dir / "task-tsdz_acq-7-likert_survey.json").write_text(
        '{"Study": {"TaskName": "tsdz_acq-7-likert"}}\n',
        encoding="utf-8",
    )
    (project_dir / "task-tsdz_acq-10-likert_survey.json").write_text(
        '{"Study": {"TaskName": "tsdz_acq-10-likert"}}\n',
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-01_task-tsdz_acq-7-likert_survey.tsv").write_text(
        "participant_id\tvalue\nsub-001\t1\n",
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-01_task-tsdz_acq-7-likert_survey.json").write_text(
        '{"Study": {"TaskName": "tsdz_acq-7-likert"}}\n',
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-01_task-tsdz_acq-10-likert_survey.tsv").write_text(
        "participant_id\tvalue\nsub-001\t2\n",
        encoding="utf-8",
    )
    (survey_dir / "sub-001_ses-01_task-tsdz_acq-10-likert_survey.json").write_text(
        '{"Study": {"TaskName": "tsdz_acq-10-likert"}}\n',
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_complex_survey_task_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        exclude_tasks={"survey": {"tsdz_acq-10-likert"}},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "sub-001/ses-01/survey/sub-001_ses-01_task-tsdz_acq-10-likert_survey.tsv" not in names
    assert "sub-001/ses-01/survey/sub-001_ses-01_task-tsdz_acq-10-likert_survey.json" not in names
    assert "task-tsdz_acq-10-likert_survey.json" not in names
    assert "sub-001/ses-01/survey/sub-001_ses-01_task-tsdz_acq-7-likert_survey.tsv" in names
    assert "sub-001/ses-01/survey/sub-001_ses-01_task-tsdz_acq-7-likert_survey.json" in names
    assert "task-tsdz_acq-7-likert_survey.json" in names


def test_export_can_exclude_anat_suffix_labels(tmp_path):
    project_dir = tmp_path / "study"
    anat_dir = project_dir / "sub-001" / "ses-01" / "anat"
    anat_dir.mkdir(parents=True)

    (anat_dir / "sub-001_ses-01_T1w.nii.gz").write_bytes(b"nifti-t1")
    (anat_dir / "sub-001_ses-01_T2w.nii.gz").write_bytes(b"nifti-t2")

    output_zip = tmp_path / "export_anat_suffix_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        exclude_acq={"anat": {"T1w"}},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "sub-001/ses-01/anat/sub-001_ses-01_T1w.nii.gz" not in names
    assert "sub-001/ses-01/anat/sub-001_ses-01_T2w.nii.gz" in names


def test_export_can_exclude_nested_derivative_anat_suffix_labels(tmp_path):
    project_dir = tmp_path / "study"
    anat_dir = project_dir / "derivatives" / "pipeline" / "sub-001" / "ses-01" / "anat"
    anat_dir.mkdir(parents=True)

    (anat_dir / "sub-001_ses-01_T1w.nii.gz").write_bytes(b"nifti-t1")
    (anat_dir / "sub-001_ses-01_T2w.nii.gz").write_bytes(b"nifti-t2")
    (anat_dir / "sub-001_ses-01_acq-PDw_echo-5_flip-4_mt-off_MPM.nii.gz").write_bytes(b"nifti-mpm")

    output_zip = tmp_path / "export_derivative_anat_suffix_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=True,
        include_code=False,
        include_analysis=False,
        exclude_acq={"anat": {"T2w", "MPM"}},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "derivatives/pipeline/sub-001/ses-01/anat/sub-001_ses-01_T1w.nii.gz" in names
    assert "derivatives/pipeline/sub-001/ses-01/anat/sub-001_ses-01_T2w.nii.gz" not in names
    assert "derivatives/pipeline/sub-001/ses-01/anat/sub-001_ses-01_acq-PDw_echo-5_flip-4_mt-off_MPM.nii.gz" not in names


def test_export_can_exclude_dwi_suffix_labels(tmp_path):
    project_dir = tmp_path / "study"
    dwi_dir = project_dir / "sub-001" / "ses-01" / "dwi"
    dwi_dir.mkdir(parents=True)

    (dwi_dir / "sub-001_ses-01_acq-shell1_dwi.nii.gz").write_bytes(b"nifti-dwi")
    (dwi_dir / "sub-001_ses-01_sbref.nii.gz").write_bytes(b"nifti-sbref")

    output_zip = tmp_path / "export_dwi_suffix_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        exclude_acq={"dwi": {"sbref"}},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "sub-001/ses-01/dwi/sub-001_ses-01_sbref.nii.gz" not in names
    assert "sub-001/ses-01/dwi/sub-001_ses-01_acq-shell1_dwi.nii.gz" in names


def test_export_can_exclude_fmap_suffix_labels(tmp_path):
    project_dir = tmp_path / "study"
    fmap_dir = project_dir / "sub-001" / "ses-01" / "fmap"
    fmap_dir.mkdir(parents=True)

    (fmap_dir / "sub-001_ses-01_dir-AP_epi.nii.gz").write_bytes(b"nifti-epi")
    (fmap_dir / "sub-001_ses-01_acq-gre_magnitude1.nii.gz").write_bytes(b"nifti-mag")

    output_zip = tmp_path / "export_fmap_suffix_filtered.zip"

    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        exclude_acq={"fmap": {"epi"}},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "sub-001/ses-01/fmap/sub-001_ses-01_dir-AP_epi.nii.gz" not in names
    assert "sub-001/ses-01/fmap/sub-001_ses-01_acq-gre_magnitude1.nii.gz" in names


def test_export_can_strip_version_control_metadata_for_upload_ready_shares(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n",
        encoding="utf-8",
    )
    (project_dir / "dataset_description.json").write_text(
        '{"Name": "Demo", "BIDSVersion": "1.10.1"}\n', encoding="utf-8"
    )
    (project_dir / ".bidsignore").write_text("*.log\n", encoding="utf-8")
    (project_dir / ".gitattributes").write_text("* annex.largefiles=anything\n", encoding="utf-8")
    (project_dir / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
    (project_dir / "CHANGES").write_text("Initial DataLad state\n", encoding="utf-8")

    code_dir = project_dir / "code"
    code_dir.mkdir(parents=True)
    (code_dir / "some_script.py").write_text("print('ok')\n", encoding="utf-8")
    (code_dir / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    (code_dir / ".datalad").mkdir(parents=True)
    (code_dir / ".datalad" / "config").write_text("[datalad]\n", encoding="utf-8")

    subject_dir = project_dir / "sub-001" / "beh"
    subject_dir.mkdir(parents=True)
    (subject_dir / "sub-001_task-test_events.tsv").write_text(
        "participant_id\tvalue\nsub-001\t1\n",
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_upload_ready.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=True,
        include_analysis=False,
        exclude_version_control_metadata=True,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "dataset_description.json" in names
    assert ".bidsignore" in names
    assert "code/some_script.py" in names
    assert "sub-001/beh/sub-001_task-test_events.tsv" in names
    assert ".gitattributes" not in names
    assert ".gitignore" not in names
    assert "CHANGES" not in names
    assert "code/.gitignore" not in names
    assert all("/.datalad/" not in name for name in names)


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


def test_export_saves_anonymization_map_to_project_code_directory(tmp_path):
    """Mapping file must be written to project/code/ and not deleted after export."""
    project_dir = tmp_path / "study"
    (project_dir / "sub-001").mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n",
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

    mapping_path = project_dir / "code" / "anonymization_map.json"
    assert mapping_path.exists(), "anonymization_map.json must exist in project/code/"
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert "mapping" in data
    assert "sub-001" in data["mapping"]
    assert stats["mapping_file"] == str(mapping_path)


def test_export_anonymization_map_excluded_from_zip(tmp_path):
    """anonymization_map.json must never appear in the exported ZIP."""
    project_dir = tmp_path / "study"
    code_dir = project_dir / "code"
    code_dir.mkdir(parents=True)
    (project_dir / "sub-001").mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n",
        encoding="utf-8",
    )
    # Pre-create the mapping file to ensure _add_tree sees it
    (code_dir / "anonymization_map.json").write_text(
        '{"mapping": {}}', encoding="utf-8"
    )
    (code_dir / "some_script.py").write_text("# code\n", encoding="utf-8")

    output_zip = tmp_path / "export.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=True,
        deterministic=True,
        include_derivatives=False,
        include_code=True,
        include_analysis=False,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = archive.namelist()

    assert all("anonymization_map.json" not in name for name in names)
    assert any("some_script.py" in name for name in names)


def test_export_no_anonymization_mapping_file_key_is_none(tmp_path):
    """When anonymize=False the stats mapping_file key must be None."""
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n",
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_nonanon.zip"
    stats = export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    assert stats["mapping_file"] is None
    assert not (project_dir / "code" / "anonymization_map.json").exists()


def test_export_anonymize_rewrites_subject_id_columns_in_tsv(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\nsub-002\t31\n",
        encoding="utf-8",
    )

    sub_dir = project_dir / "sub-001" / "beh"
    sub_dir.mkdir(parents=True)
    source_name = "sub-001_task-demo_records.tsv"
    (sub_dir / source_name).write_text(
        "subject_id\tvalue\nsub-001\t1\nsub-002\t2\n",
        encoding="utf-8",
    )

    expected_mapping = create_participant_mapping(
        ["sub-001", "sub-002"],
        tmp_path / "mapping.json",
        id_length=6,
        deterministic=True,
    )

    output_zip = tmp_path / "export_subject_id.zip"
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

    sub001_anon = expected_mapping["sub-001"]

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())
        tsv_data = archive.read(
            f"{sub001_anon}/beh/{sub001_anon}_task-demo_records.tsv"
        ).decode("utf-8")

    assert f"{sub001_anon}/beh/{sub001_anon}_task-demo_records.tsv" in names
    assert "sub-001" not in tsv_data
    assert "sub-002" not in tsv_data
    assert expected_mapping["sub-001"] in tsv_data
    assert expected_mapping["sub-002"] in tsv_data


def test_export_anonymize_rewrites_recursive_json_string_paths(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-01\t30\nsub-010\t31\n",
        encoding="utf-8",
    )

    func_dir = project_dir / "sub-010" / "func"
    fmap_dir = project_dir / "sub-010" / "fmap"
    func_dir.mkdir(parents=True)
    fmap_dir.mkdir(parents=True)

    (func_dir / "sub-010_task-rest_bold.nii.gz").write_bytes(b"dummy")
    (fmap_dir / "sub-010_dir-AP_epi.json").write_text(
        json.dumps(
            {
                "IntendedFor": "sub-010/func/sub-010_task-rest_bold.nii.gz",
                "Sources": [
                    "bids::sub-010/func/sub-010_task-rest_bold.nii.gz",
                    "legacy/sub-010/func/sub-010_task-rest_bold.nii.gz",
                ],
                "Nested": {
                    "Path": "derivatives/sub-010/fmap/sub-010_dir-AP_epi.nii.gz",
                },
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

    output_zip = tmp_path / "export_recursive_json.zip"
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
        data = json.loads(
            archive.read(f"{sub010_anon}/fmap/{sub010_anon}_dir-AP_epi.json").decode(
                "utf-8"
            )
        )

    assert data["IntendedFor"] == f"{sub010_anon}/func/{sub010_anon}_task-rest_bold.nii.gz"
    assert data["Sources"][0] == f"bids::{sub010_anon}/func/{sub010_anon}_task-rest_bold.nii.gz"
    assert data["Sources"][1] == f"legacy/{sub010_anon}/func/{sub010_anon}_task-rest_bold.nii.gz"
    assert data["Nested"]["Path"] == f"derivatives/{sub010_anon}/fmap/{sub010_anon}_dir-AP_epi.nii.gz"
    assert malformed_sub010 not in json.dumps(data)


def test_export_scrub_mri_json_removes_sensitive_sidecar_fields(tmp_path):
    project_dir = tmp_path / "study"
    anat_dir = project_dir / "sub-001" / "anat"
    anat_dir.mkdir(parents=True)

    (anat_dir / "sub-001_T1w.json").write_text(
        json.dumps(
            {
                "StationName": "Scanner-123",
                "DeviceSerialNumber": "ABC-999",
                "EchoTime": 0.003,
            }
        ),
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_scrub_json.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        scrub_mri_json=True,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        sidecar = json.loads(
            archive.read("sub-001/anat/sub-001_T1w.json").decode("utf-8")
        )

    assert "StationName" not in sidecar
    assert "DeviceSerialNumber" not in sidecar
    assert sidecar["EchoTime"] == 0.003


def test_export_clean_nifti_gzip_headers_normalizes_mtime_and_fname(tmp_path):
    project_dir = tmp_path / "study"
    func_dir = project_dir / "sub-001" / "func"
    func_dir.mkdir(parents=True)

    original_payload = b"demo-nifti-payload"
    source_nifti = func_dir / "sub-001_task-rest_bold.nii.gz"
    with source_nifti.open("wb") as fh:
        with gzip.GzipFile(
            filename="original_name.nii",
            mode="wb",
            fileobj=fh,
            mtime=1_700_000_000,
        ) as gz_out:
            gz_out.write(original_payload)

    original_bytes = source_nifti.read_bytes()
    assert int.from_bytes(original_bytes[4:8], "little") != 0
    assert (original_bytes[3] & 0x08) != 0

    output_zip = tmp_path / "export_clean_nifti.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        clean_nifti_gzip_headers=True,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        exported_nifti = archive.read("sub-001/func/sub-001_task-rest_bold.nii.gz")

    assert int.from_bytes(exported_nifti[4:8], "little") == 0
    assert (exported_nifti[3] & 0x08) == 0

    with gzip.GzipFile(fileobj=io.BytesIO(exported_nifti), mode="rb") as gz_in:
        assert gz_in.read() == original_payload


def test_export_root_nifti_gzip_header_cleaning_via_scrub_option(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True)

    original_payload = b"root-nifti-payload"
    root_nifti = project_dir / "phantom.nii.gz"
    with root_nifti.open("wb") as fh:
        with gzip.GzipFile(
            filename="phantom_orig.nii",
            mode="wb",
            fileobj=fh,
            mtime=1_700_000_100,
        ) as gz_out:
            gz_out.write(original_payload)

    output_zip = tmp_path / "export_root_nifti_clean.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        scrub_mri_json=True,
        clean_nifti_gzip_headers=True,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        exported_nifti = archive.read("phantom.nii.gz")

    assert int.from_bytes(exported_nifti[4:8], "little") == 0
    assert (exported_nifti[3] & 0x08) == 0
    with gzip.GzipFile(fileobj=io.BytesIO(exported_nifti), mode="rb") as gz_in:
        assert gz_in.read() == original_payload


def test_export_nifti_gzip_headers_unchanged_when_cleaning_disabled(tmp_path):
    project_dir = tmp_path / "study"
    func_dir = project_dir / "sub-001" / "func"
    func_dir.mkdir(parents=True)

    source_nifti = func_dir / "sub-001_task-rest_bold.nii.gz"
    with source_nifti.open("wb") as fh:
        with gzip.GzipFile(
            filename="keep_header_name.nii",
            mode="wb",
            fileobj=fh,
            mtime=1_700_000_200,
        ) as gz_out:
            gz_out.write(b"unchanged-payload")

    original_bytes = source_nifti.read_bytes()
    original_mtime = int.from_bytes(original_bytes[4:8], "little")
    original_has_fname = (original_bytes[3] & 0x08) != 0
    assert original_mtime != 0
    assert original_has_fname is True

    output_zip = tmp_path / "export_nifti_no_clean.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        clean_nifti_gzip_headers=False,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        exported_nifti = archive.read("sub-001/func/sub-001_task-rest_bold.nii.gz")

    assert int.from_bytes(exported_nifti[4:8], "little") == original_mtime
    assert ((exported_nifti[3] & 0x08) != 0) is original_has_fname


def test_export_scrub_mri_json_mixed_modality_tree_preserves_non_mri(tmp_path):
    project_dir = tmp_path / "study"

    anat_dir = project_dir / "sub-001" / "ses-01" / "anat"
    func_dir = project_dir / "sub-001" / "ses-01" / "func"
    dwi_dir = project_dir / "sub-001" / "ses-01" / "dwi"
    fmap_dir = project_dir / "sub-001" / "ses-01" / "fmap"
    eeg_dir = project_dir / "sub-001" / "ses-01" / "eeg"
    for folder in (anat_dir, func_dir, dwi_dir, fmap_dir, eeg_dir):
        folder.mkdir(parents=True)

    (anat_dir / "sub-001_ses-01_T1w.json").write_text(
        json.dumps(
            {
                "StationName": "ANAT-Scanner",
                "PatientName": "Sensitive Name",
                "ImageOrientationPatientDICOM": [1, 0, 0, 0, 1, 0],
                "EchoTime": 0.003,
            }
        ),
        encoding="utf-8",
    )
    (func_dir / "sub-001_ses-01_task-rest_bold.json").write_text(
        json.dumps(
            {
                "StationName": "FUNC-Scanner",
                "PatientName": "Keep In FUNC",
                "ImageOrientationPatientDICOM": [1, 0, 0, 0, 1, 0],
                "RepetitionTime": 2.0,
            }
        ),
        encoding="utf-8",
    )
    (dwi_dir / "sub-001_ses-01_dwi.json").write_text(
        json.dumps(
            {
                "DeviceSerialNumber": "DWI-123",
                "ImageOrientationPatientDICOM": [1, 0, 0, 0, 1, 0],
                "TotalReadoutTime": 0.04,
            }
        ),
        encoding="utf-8",
    )
    (fmap_dir / "sub-001_ses-01_dir-AP_epi.json").write_text(
        json.dumps(
            {
                "StationName": "FMAP-Scanner",
                "ImageOrientationPatientDICOM": [1, 0, 0, 0, 1, 0],
                "IntendedFor": "sub-001/ses-01/func/sub-001_ses-01_task-rest_bold.nii.gz",
            }
        ),
        encoding="utf-8",
    )
    (eeg_dir / "sub-001_ses-01_task-rest_eeg.json").write_text(
        json.dumps(
            {
                "StationName": "EEG-Scanner",
                "Manufacturer": "Acme EEG",
            }
        ),
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_mixed_modalities_scrub.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        scrub_mri_json=True,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        anat = json.loads(
            archive.read("sub-001/ses-01/anat/sub-001_ses-01_T1w.json").decode("utf-8")
        )
        func = json.loads(
            archive.read("sub-001/ses-01/func/sub-001_ses-01_task-rest_bold.json").decode(
                "utf-8"
            )
        )
        dwi = json.loads(
            archive.read("sub-001/ses-01/dwi/sub-001_ses-01_dwi.json").decode("utf-8")
        )
        fmap = json.loads(
            archive.read("sub-001/ses-01/fmap/sub-001_ses-01_dir-AP_epi.json").decode(
                "utf-8"
            )
        )
        eeg = json.loads(
            archive.read("sub-001/ses-01/eeg/sub-001_ses-01_task-rest_eeg.json").decode(
                "utf-8"
            )
        )

    assert "StationName" not in anat
    assert "PatientName" not in anat
    assert "ImageOrientationPatientDICOM" not in anat
    assert anat["EchoTime"] == 0.003

    assert "StationName" not in func
    assert "ImageOrientationPatientDICOM" not in func
    assert "PatientName" not in func
    assert func["RepetitionTime"] == 2.0

    assert "DeviceSerialNumber" not in dwi
    assert "ImageOrientationPatientDICOM" not in dwi
    assert dwi["TotalReadoutTime"] == 0.04

    assert "StationName" not in fmap
    assert "ImageOrientationPatientDICOM" not in fmap
    assert fmap["IntendedFor"] == "sub-001/ses-01/func/sub-001_ses-01_task-rest_bold.nii.gz"

    # Non-MRI sidecars must remain untouched by MRI scrub mode.
    assert eeg["StationName"] == "EEG-Scanner"
    assert eeg["Manufacturer"] == "Acme EEG"


def test_export_scrub_mri_json_custom_group_selection(tmp_path):
    project_dir = tmp_path / "study"
    anat_dir = project_dir / "sub-001" / "anat"
    anat_dir.mkdir(parents=True)

    (anat_dir / "sub-001_T1w.json").write_text(
        json.dumps(
            {
                "StationName": "Scanner-123",
                "PatientName": "Sensitive Name",
                "EchoTime": 0.003,
            }
        ),
        encoding="utf-8",
    )

    output_zip = tmp_path / "export_scrub_custom_groups.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
        scrub_mri_json=True,
        scrub_mri_json_groups={"scanner_site"},
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        sidecar = json.loads(
            archive.read("sub-001/anat/sub-001_T1w.json").decode("utf-8")
        )

    assert "StationName" not in sidecar
    # PatientName belongs to a different scrub group and should remain.
    assert sidecar["PatientName"] == "Sensitive Name"
    assert sidecar["EchoTime"] == 0.003


def test_export_clean_nifti_gzip_headers_handles_nested_and_derivative_paths(tmp_path):
    project_dir = tmp_path / "study"

    long_stem = (
        "sub-001_ses-verylongsessionlabel_task-verylongtaskname"
        "_acq-ultralongacquisitionlabel_run-01_desc-ultralongdescriptor_bold"
    )

    nested_sources = {
        project_dir
        / "sub-001"
        / "ses-verylongsessionlabel"
        / "func"
        / f"{long_stem}.nii.gz": b"func-payload",
        project_dir
        / "sub-001"
        / "ses-verylongsessionlabel"
        / "dwi"
        / "sub-001_ses-verylongsessionlabel_dir-AP_dwi.nii.gz": b"dwi-payload",
        project_dir
        / "derivatives"
        / "qc"
        / "sub-001"
        / "ses-verylongsessionlabel"
        / "func"
        / f"{long_stem}_desc-qc.nii.gz": b"derivative-payload",
    }

    for index, (path, payload) in enumerate(nested_sources.items(), start=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            with gzip.GzipFile(
                filename=f"source-{index}.nii",
                mode="wb",
                fileobj=fh,
                mtime=1_700_010_000 + index,
            ) as gz_out:
                gz_out.write(payload)

    output_zip = tmp_path / "export_nested_nifti_clean.zip"
    export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        mask_questions=False,
        include_derivatives=True,
        include_code=False,
        include_analysis=False,
        clean_nifti_gzip_headers=True,
    )

    with zipfile.ZipFile(output_zip, "r") as archive:
        for source_path, expected_payload in nested_sources.items():
            arcname = str(source_path.relative_to(project_dir))
            exported_nifti = archive.read(arcname)

            assert int.from_bytes(exported_nifti[4:8], "little") == 0
            assert (exported_nifti[3] & 0x08) == 0

            with gzip.GzipFile(fileobj=io.BytesIO(exported_nifti), mode="rb") as gz_in:
                assert gz_in.read() == expected_payload


def test_export_sourcedata_is_excluded_by_default_and_included_when_requested(tmp_path):
    project_dir = tmp_path / "study"
    sourcedata_file = project_dir / "sourcedata" / "survey" / "demo.csv"
    sourcedata_file.parent.mkdir(parents=True, exist_ok=True)
    sourcedata_file.write_text("participant_id,value\nsub-001,1\n", encoding="utf-8")

    default_zip = tmp_path / "export_default.zip"
    export_project(
        project_path=project_dir,
        output_zip=default_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    with zipfile.ZipFile(default_zip, "r") as archive:
        names = set(archive.namelist())
    assert "sourcedata/survey/demo.csv" not in names

    with_sourcedata_zip = tmp_path / "export_with_sourcedata.zip"
    export_project(
        project_path=project_dir,
        output_zip=with_sourcedata_zip,
        anonymize=False,
        include_derivatives=False,
        include_sourcedata=True,
        include_code=False,
        include_analysis=False,
    )

    with zipfile.ZipFile(with_sourcedata_zip, "r") as archive:
        names = set(archive.namelist())
    assert "sourcedata/survey/demo.csv" in names


def test_export_skips_unfetched_datalad_symlinks_instead_of_crashing(tmp_path):
    """Regression guard: DataLad-tracked .nii.gz/.edf files are normally
    symlinks into .git/annex/objects/. Before content has been fetched,
    the symlink is broken — os.stat() (used internally by zipfile) raises
    an unhandled FileNotFoundError on it. The export must skip such files
    with a clear record instead of crashing the entire export."""
    project_dir = tmp_path / "study"
    anat_dir = project_dir / "sub-001" / "anat"
    anat_dir.mkdir(parents=True)

    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n", encoding="utf-8"
    )
    real_file = anat_dir / "sub-001_T1w.json"
    real_file.write_text("{}", encoding="utf-8")

    broken_symlink = anat_dir / "sub-001_T1w.nii.gz"
    broken_symlink.symlink_to(
        project_dir / ".git" / "annex" / "objects" / "missing.nii.gz"
    )
    assert not broken_symlink.exists()

    output_zip = tmp_path / "export_with_unfetched_content.zip"

    summary = export_project(
        project_path=project_dir,
        output_zip=output_zip,
        anonymize=False,
        include_derivatives=False,
        include_code=False,
        include_analysis=False,
    )

    assert output_zip.exists()
    assert summary["files_skipped_unfetched"] == 1
    assert any("sub-001_T1w.nii.gz" in path for path in summary["unfetched_files"])

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = archive.namelist()
    assert "sub-001/anat/sub-001_T1w.json" in names
    assert not any(name.endswith("sub-001_T1w.nii.gz") for name in names)
