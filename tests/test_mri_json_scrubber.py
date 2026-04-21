"""Tests for src/mri_json_scrubber.py — privacy-sensitive field scrubbing."""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.mri_json_scrubber import (
    scrub_sensitive_json_fields,
    scrub_json_file,
    detect_modality_from_path,
    is_mri_json_sidecar,
    is_anatomical_defaced,
    scan_mri_jsons,
    build_defacing_report,
    _has_defaced_filename,
    ALWAYS_SCRUB,
    ANAT_EXTRA_SCRUB,
)
from pathlib import Path


# ---------------------------------------------------------------------------
# scrub_sensitive_json_fields
# ---------------------------------------------------------------------------

class TestScrubSensitiveJsonFields:
    def test_removes_always_scrub_fields(self):
        data = {"DeviceSerialNumber": "12345", "RepetitionTime": 2.0}
        scrubbed, removed = scrub_sensitive_json_fields(data)
        assert "DeviceSerialNumber" not in scrubbed
        assert "RepetitionTime" in scrubbed
        assert "DeviceSerialNumber" in removed

    def test_case_insensitive_matching(self):
        data = {"deviceSERIALnumber": "abc", "TR": 1.0}
        scrubbed, removed = scrub_sensitive_json_fields(data)
        assert "deviceSERIALnumber" not in scrubbed
        assert len(removed) == 1

    def test_no_sensitive_fields_untouched(self):
        data = {"RepetitionTime": 2.0, "FlipAngle": 90}
        scrubbed, removed = scrub_sensitive_json_fields(data)
        assert scrubbed == data
        assert removed == []

    def test_anat_modality_removes_extra_fields(self):
        data = {"PatientName": "John", "RepetitionTime": 2.0}
        scrubbed, removed = scrub_sensitive_json_fields(data, modality="anat")
        assert "PatientName" not in scrubbed
        assert "PatientName" in removed

    def test_non_mri_modality_does_not_remove_anat_fields(self):
        data = {"PatientName": "John"}
        scrubbed, removed = scrub_sensitive_json_fields(data, modality="survey")
        # PatientName is not in ALWAYS_SCRUB, only in ANAT_EXTRA_SCRUB
        assert "PatientName" in scrubbed

    def test_extra_fields_removed(self):
        data = {"CustomSensitive": "secret", "OK": "fine"}
        scrubbed, removed = scrub_sensitive_json_fields(data, extra_fields={"CustomSensitive"})
        assert "CustomSensitive" not in scrubbed
        assert "OK" in scrubbed

    def test_empty_data(self):
        scrubbed, removed = scrub_sensitive_json_fields({})
        assert scrubbed == {}
        assert removed == []

    def test_all_always_scrub_fields_removed(self):
        data = {field: "value" for field in ALWAYS_SCRUB}
        scrubbed, removed = scrub_sensitive_json_fields(data)
        assert scrubbed == {}
        assert set(removed) == ALWAYS_SCRUB


# ---------------------------------------------------------------------------
# scrub_json_file
# ---------------------------------------------------------------------------

class TestScrubJsonFile:
    def test_loads_and_scrubs(self, tmp_path):
        sidecar = {"StationName": "scanner1", "RepetitionTime": 2.0}
        json_path = tmp_path / "sub-01_T1w.json"
        json_path.write_text(json.dumps(sidecar))
        scrubbed, removed = scrub_json_file(json_path)
        assert "StationName" not in scrubbed
        assert "RepetitionTime" in scrubbed

    def test_modality_passed_through(self, tmp_path):
        sidecar = {"PatientName": "Alice", "TR": 1.0}
        json_path = tmp_path / "sub-01_T1w.json"
        json_path.write_text(json.dumps(sidecar))
        scrubbed, removed = scrub_json_file(json_path, modality="anat")
        assert "PatientName" not in scrubbed


# ---------------------------------------------------------------------------
# detect_modality_from_path
# ---------------------------------------------------------------------------

class TestDetectModalityFromPath:
    def test_anat(self):
        p = Path("/data/sub-01/ses-01/anat/sub-01_T1w.json")
        assert detect_modality_from_path(p) == "anat"

    def test_func(self):
        p = Path("/data/sub-01/func/sub-01_bold.json")
        assert detect_modality_from_path(p) == "func"

    def test_dwi(self):
        p = Path("/data/sub-01/dwi/sub-01_dwi.json")
        assert detect_modality_from_path(p) == "dwi"

    def test_fmap(self):
        p = Path("/data/sub-01/fmap/sub-01_phasediff.json")
        assert detect_modality_from_path(p) == "fmap"

    def test_unknown_modality(self):
        p = Path("/data/sub-01/survey/sub-01_survey.json")
        assert detect_modality_from_path(p) is None


# ---------------------------------------------------------------------------
# is_mri_json_sidecar
# ---------------------------------------------------------------------------

class TestIsMriJsonSidecar:
    def test_anat_json_is_mri(self):
        assert is_mri_json_sidecar(Path("/data/sub-01/anat/sub-01_T1w.json"))

    def test_non_json_is_not_mri(self):
        assert not is_mri_json_sidecar(Path("/data/sub-01/anat/sub-01_T1w.nii.gz"))

    def test_survey_json_is_not_mri(self):
        assert not is_mri_json_sidecar(Path("/data/sub-01/survey/sub-01_survey.json"))


# ---------------------------------------------------------------------------
# _has_defaced_filename
# ---------------------------------------------------------------------------

class TestHasDefacedFilename:
    def test_defaced_suffix(self):
        assert _has_defaced_filename(Path("sub-01_T1w_defaced.nii.gz"))

    def test_desc_defaced(self):
        assert _has_defaced_filename(Path("sub-01_desc-defaced_T1w.nii.gz"))

    def test_brain_suffix(self):
        assert _has_defaced_filename(Path("sub-01_T1w_brain.nii.gz"))

    def test_normal_filename(self):
        assert not _has_defaced_filename(Path("sub-01_T1w.nii.gz"))


# ---------------------------------------------------------------------------
# is_anatomical_defaced
# ---------------------------------------------------------------------------

class TestIsAnatomicalDefaced:
    def test_no_nifti_returns_unknown(self, tmp_path):
        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text("{}")
        result = is_anatomical_defaced(sidecar)
        assert result["status"] == "unknown"
        assert result["nifti_found"] is False

    def test_defaced_filename_detected(self, tmp_path):
        # JSON and NIfTI share the same stem; defacing marker is in that stem
        sidecar = tmp_path / "sub-01_desc-defaced_T1w.json"
        sidecar.write_text("{}")
        nifti = tmp_path / "sub-01_desc-defaced_T1w.nii.gz"
        nifti.touch()
        result = is_anatomical_defaced(sidecar, check_nibabel=False)
        assert result["status"] == "defaced"
        assert result["nifti_found"] is True

    def test_normal_nifti_unknown_without_nibabel(self, tmp_path):
        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text("{}")
        nifti = tmp_path / "sub-01_T1w.nii.gz"
        nifti.touch()
        result = is_anatomical_defaced(sidecar, check_nibabel=False)
        assert result["status"] == "unknown"
        assert result["nifti_found"] is True


# ---------------------------------------------------------------------------
# scan_mri_jsons
# ---------------------------------------------------------------------------

class TestScanMriJsons:
    def test_finds_mri_jsons(self, tmp_path):
        anat = tmp_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-01_T1w.json").write_text("{}")
        # non-MRI file should not appear
        (anat / "sub-01_T1w.nii.gz").touch()
        results = scan_mri_jsons(tmp_path)
        assert len(results) == 1
        assert results[0].name == "sub-01_T1w.json"

    def test_non_subject_dirs_ignored(self, tmp_path):
        code = tmp_path / "code" / "anat"
        code.mkdir(parents=True)
        (code / "sub-01_T1w.json").write_text("{}")
        results = scan_mri_jsons(tmp_path)
        assert results == []


# ---------------------------------------------------------------------------
# build_defacing_report
# ---------------------------------------------------------------------------

class TestBuildDefacingReport:
    def test_empty_project(self, tmp_path):
        report = build_defacing_report(tmp_path)
        assert report == []

    def test_anat_json_appears_in_report(self, tmp_path):
        anat = tmp_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-01_T1w.json").write_text("{}")
        report = build_defacing_report(tmp_path)
        assert len(report) == 1
        assert "file" in report[0]
        assert report[0]["status"] in ("defaced", "not_defaced", "unknown")

    def test_non_anat_json_not_included(self, tmp_path):
        func = tmp_path / "sub-01" / "func"
        func.mkdir(parents=True)
        (func / "sub-01_task-rest_bold.json").write_text("{}")
        report = build_defacing_report(tmp_path)
        assert report == []


# ---------------------------------------------------------------------------
# _nibabel_defacing_heuristic mocked tests (lines 224-240)
# ---------------------------------------------------------------------------

class TestNibabelDefacingHeuristic:
    def test_nibabel_heuristic_defaced_header(self, tmp_path, monkeypatch):
        """Lines 224-240: mock nibabel to return defacing header."""
        from src import mri_json_scrubber
        nifti = tmp_path / "sub-01_T1w.nii.gz"
        nifti.touch()

        class MockHeader:
            def __getitem__(self, key):
                return b"defaced image"

        class MockImg:
            header = MockHeader()

        class MockNib:
            @staticmethod
            def load(path):
                return MockImg()

        monkeypatch.setattr(mri_json_scrubber, "_nibabel_defacing_heuristic",
                            lambda p: True)

        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text("{}")
        result = is_anatomical_defaced(sidecar, check_nibabel=True)
        assert result["status"] == "defaced"

    def test_nibabel_heuristic_header_no_marker(self, tmp_path, monkeypatch):
        """Lines 292-296: nibabel says not defaced → not_defaced."""
        from src import mri_json_scrubber
        nifti = tmp_path / "sub-01_T1w.nii.gz"
        nifti.touch()
        monkeypatch.setattr(mri_json_scrubber, "_nibabel_defacing_heuristic",
                            lambda p: False)
        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text("{}")
        result = is_anatomical_defaced(sidecar, check_nibabel=True)
        assert result["status"] == "not_defaced"

    def test_nibabel_not_available_returns_none(self, tmp_path, monkeypatch):
        """Lines 239-240: nibabel heuristic fails → returns None."""
        from src import mri_json_scrubber
        nifti = tmp_path / "sub-01_T1w.nii.gz"
        nifti.touch()
        monkeypatch.setattr(mri_json_scrubber, "_nibabel_defacing_heuristic",
                            lambda p: None)
        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text("{}")
        result = is_anatomical_defaced(sidecar, check_nibabel=True)
        # None means nibabel not available → status should be unknown
        assert result["status"] == "unknown"
