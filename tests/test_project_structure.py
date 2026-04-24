"""Tests for src/project_structure.py — BIDS/PRISM project directory scanner."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.project_structure import (
    get_project_modalities_and_sessions,
    get_project_quick_summary,
    _extract_acq,
)


class TestExtractAcq:
    def test_present(self):
        assert _extract_acq("sub-01_ses-01_acq-highres_T1w.json") == "highres"

    def test_absent(self):
        assert _extract_acq("sub-01_T1w.json") is None

    def test_numeric_acq(self):
        assert _extract_acq("sub-01_acq-64ch_bold.json") == "64ch"


class TestGetProjectModalitiesAndSessions:
    def test_empty_project(self, tmp_path):
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["sessions"] == []
        assert result["modalities"] == []
        assert result["acq_labels"] == {}

    def test_non_subject_dirs_ignored(self, tmp_path):
        (tmp_path / "code").mkdir()
        (tmp_path / "derivatives").mkdir()
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["modalities"] == []

    def test_sessionless_layout(self, tmp_path):
        sub = tmp_path / "sub-01" / "eeg"
        sub.mkdir(parents=True)
        (sub / "sub-01_task-rest_eeg.set").touch()
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["sessions"] == []
        assert "eeg" in result["modalities"]

    def test_session_layout(self, tmp_path):
        mod = tmp_path / "sub-01" / "ses-01" / "func"
        mod.mkdir(parents=True)
        (mod / "sub-01_ses-01_task-rest_bold.nii.gz").touch()
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["sessions"] == ["ses-01"]
        assert "func" in result["modalities"]

    def test_multiple_sessions_sorted(self, tmp_path):
        for ses in ["ses-02", "ses-01"]:
            (tmp_path / "sub-01" / ses / "eeg").mkdir(parents=True)
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["sessions"] == ["ses-01", "ses-02"]

    def test_acq_labels_collected(self, tmp_path):
        mod = tmp_path / "sub-01" / "ses-01" / "func"
        mod.mkdir(parents=True)
        (mod / "sub-01_ses-01_acq-standard_bold.nii.gz").touch()
        (mod / "sub-01_ses-01_acq-highres_bold.nii.gz").touch()
        result = get_project_modalities_and_sessions(tmp_path)
        assert sorted(result["acq_labels"]["func"]) == ["highres", "standard"]

    def test_hidden_dirs_ignored(self, tmp_path):
        (tmp_path / "sub-01" / ".git").mkdir(parents=True)
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["modalities"] == []

    def test_multiple_subjects_merged(self, tmp_path):
        for sub in ["sub-01", "sub-02"]:
            (tmp_path / sub / "survey").mkdir(parents=True)
        result = get_project_modalities_and_sessions(tmp_path)
        assert result["modalities"] == ["survey"]

    def test_file_directly_in_subject_dir_ignored(self, tmp_path):
        """Line 49: child.is_dir() guard skips files in sub- dir."""
        sub = tmp_path / "sub-01"
        sub.mkdir()
        (sub / "README.txt").write_text("info")  # file, not dir
        (sub / "eeg").mkdir()  # also a real modality dir
        result = get_project_modalities_and_sessions(tmp_path)
        assert "eeg" in result["modalities"]

    def test_session_with_files_in_session_dir(self, tmp_path):
        """Files directly inside a ses- dir don't become modalities."""
        ses = tmp_path / "sub-01" / "ses-01"
        ses.mkdir(parents=True)
        (ses / "dataset_description.json").write_text("{}")  # file in ses dir
        (ses / "func").mkdir()  # actual modality
        result = get_project_modalities_and_sessions(tmp_path)
        assert "func" in result["modalities"]
        assert "dataset_description.json" not in result["modalities"]

    def test_scan_modality_dir_called_with_file_not_dir(self, tmp_path):
        """Line 37: _scan_modality_dir guard for non-dir path via session layout."""
        ses = tmp_path / "sub-01" / "ses-01"
        ses.mkdir(parents=True)
        # Create a file (not a dir) inside ses- dir — triggers `not modality_dir.is_dir()` guard
        (ses / "README.txt").write_text("info")
        result = get_project_modalities_and_sessions(tmp_path)
        # The file should not appear as a modality
        assert "README.txt" not in result["modalities"]
        assert result["sessions"] == ["ses-01"]


class TestGetProjectQuickSummary:
    def test_quick_summary_counts_subjects_sessions_and_modalities(self, tmp_path):
        (tmp_path / "sub-01" / "ses-01" / "func").mkdir(parents=True)
        (tmp_path / "sub-02" / "ses-01" / "eeg").mkdir(parents=True)
        (tmp_path / "dataset_description.json").write_text("{}", encoding="utf-8")

        result = get_project_quick_summary(tmp_path)

        assert result["subjects"] == 2
        assert result["sessions"] == 1
        assert result["modalities"] == 2
        assert result["session_labels"] == ["ses-01"]
        assert sorted(result["modality_labels"]) == ["eeg", "func"]
        assert result["has_dataset_description"] is True
        assert result["has_participants_tsv"] is False

    def test_quick_summary_handles_sessionless_layout(self, tmp_path):
        (tmp_path / "sub-01" / "beh").mkdir(parents=True)
        (tmp_path / "participants.tsv").write_text("participant_id\nsub-01\n", encoding="utf-8")

        result = get_project_quick_summary(tmp_path)

        assert result["subjects"] == 1
        assert result["sessions"] == 0
        assert result["modalities"] == 1
        assert result["session_labels"] == []
        assert result["modality_labels"] == ["beh"]
        assert result["has_dataset_description"] is False
        assert result["has_participants_tsv"] is True
