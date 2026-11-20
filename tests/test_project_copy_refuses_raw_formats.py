"""Raw vendor files (.vpd, .raw) are not PRISM data: they may only be copied into sourcedata/ or rawdata/,
never into a main subject folder. Every conversion funnels through copy_files_into_project."""

import pytest

from src.datalad_project_copy import copy_files_into_project


@pytest.mark.parametrize("name", ["sub-001_ses-2_recording-ecg_physio.vpd", "sub-001_task-x_physio.RAW"])
def test_raw_file_into_subject_folder_is_refused(tmp_path, name):
    src = tmp_path / "in" / name
    src.parent.mkdir()
    src.write_bytes(b"x")
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(ValueError, match="sourcedata"):
        copy_files_into_project(
            dataset_root=root, copy_pairs=[(src, root / "sub-001" / "ses-2" / "physio" / name)], run_message="m"
        )
    assert not (root / "sub-001").exists()


@pytest.mark.parametrize("folder", ["sourcedata", "rawdata"])
def test_raw_file_into_raw_folders_is_allowed(tmp_path, folder):
    src = tmp_path / "in" / "sub-001_recording-ecg_physio.vpd"
    src.parent.mkdir()
    src.write_bytes(b"x")
    root = tmp_path / "proj"
    root.mkdir()
    result = copy_files_into_project(
        dataset_root=root, copy_pairs=[(src, root / folder / "physio" / src.name)], run_message="m"
    )
    assert result["copied_count"] == 1


def test_raw_file_outside_subject_folders_is_not_this_guards_business(tmp_path):
    src = tmp_path / "in" / "x.raw"
    src.parent.mkdir()
    src.write_bytes(b"x")
    root = tmp_path / "proj"
    root.mkdir()
    result = copy_files_into_project(dataset_root=root, copy_pairs=[(src, root / "derivatives" / "x.raw")], run_message="m")
    assert result["copied_count"] == 1
