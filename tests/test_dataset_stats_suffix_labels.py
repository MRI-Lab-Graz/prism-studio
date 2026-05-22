import os
import sys


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_src_path = os.path.join(project_root, "app", "src")

if app_src_path not in sys.path:
    sys.path.insert(0, app_src_path)

from stats import DatasetStats


def test_dataset_stats_collects_anat_suffix_labels():
    stats = DatasetStats()

    stats.add_file("sub-001", "ses-1", "anat", None, "sub-001_ses-1_T1w.nii.gz")
    stats.add_file("sub-001", "ses-1", "anat", None, "sub-001_ses-1_T2w.nii.gz")

    assert sorted(stats.acq_labels.get("anat", set())) == ["T1w", "T2w"]


def test_dataset_stats_collects_dwi_suffix_and_acq_labels():
    stats = DatasetStats()

    stats.add_file(
        "sub-001",
        "ses-1",
        "dwi",
        None,
        "sub-001_ses-1_acq-shell1_dwi.nii.gz",
    )
    stats.add_file("sub-001", "ses-1", "dwi", None, "sub-001_ses-1_sbref.nii.gz")

    assert sorted(stats.acq_labels.get("dwi", set())) == ["dwi", "sbref", "shell1"]
