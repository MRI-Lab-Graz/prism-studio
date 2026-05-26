"""Tests for src/mri_json_scrubber.py — privacy-sensitive field scrubbing."""

import json
import sys
import os
import shutil
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.mri_json_scrubber import (
    scrub_sensitive_json_fields,
    scrub_json_file,
    detect_modality_from_path,
    is_mri_json_sidecar,
    is_anatomical_defaced,
    deface_anatomical_scans,
    prepare_defacing_export_copy,
    get_defacing_preflight,
    has_anatomical_data,
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

    def test_publicbids_style_sensitive_keys_removed(self):
        data = {
            "Manufacturer": "Siemens",
            "StudyInstanceUID": "1.2.3",
            "AccessionNumber": "A-123",
            "EchoTime": 0.003,
        }
        scrubbed, removed = scrub_sensitive_json_fields(data)
        assert "Manufacturer" not in scrubbed
        assert "StudyInstanceUID" not in scrubbed
        assert "AccessionNumber" not in scrubbed
        assert "EchoTime" in scrubbed
        assert "Manufacturer" in removed

    def test_pattern_sensitive_keys_removed(self):
        data = {
            "Private_ScannerTag": "secret",
            "px_hidden": "secret",
            "UserDefinedFoo": "secret",
            "SubjectCode": "sub-001",
            "TaskName": "stroop",
        }
        scrubbed, removed = scrub_sensitive_json_fields(data)
        assert "Private_ScannerTag" not in scrubbed
        assert "px_hidden" not in scrubbed
        assert "UserDefinedFoo" not in scrubbed
        assert "SubjectCode" not in scrubbed
        assert "TaskName" in scrubbed
        assert "SubjectCode" in removed

    def test_selected_groups_limit_scrubbing_scope(self):
        data = {
            "StationName": "Scanner-123",
            "PatientName": "Sensitive Name",
            "EchoTime": 0.003,
        }
        scrubbed, _removed = scrub_sensitive_json_fields(
            data,
            modality="anat",
            selected_groups={"scanner_site"},
        )
        assert "StationName" not in scrubbed
        assert scrubbed["PatientName"] == "Sensitive Name"
        assert scrubbed["EchoTime"] == 0.003


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

    def test_json_metadata_hint_marks_defaced(self, tmp_path):
        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text('{"ImageComments": "Defaced with pydeface"}')
        nifti = tmp_path / "sub-01_T1w.nii.gz"
        nifti.touch()
        result = is_anatomical_defaced(sidecar, check_nibabel=False)
        assert result["status"] == "defaced"

    def test_defacing_artifact_marks_defaced(self, tmp_path):
        sidecar = tmp_path / "sub-01_T1w.json"
        sidecar.write_text("{}")
        nifti = tmp_path / "sub-01_T1w.nii.gz"
        nifti.touch()
        (tmp_path / "sub-01_desc-defaceMask_T1w.nii.gz").touch()
        result = is_anatomical_defaced(sidecar, check_nibabel=False)
        assert result["status"] == "defaced"


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

    def test_selected_variants_filter_report_entries(self, tmp_path):
        anat = tmp_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-01_acq-mprage_T1w.json").write_text("{}")
        (anat / "sub-01_T2w.json").write_text("{}")

        report = build_defacing_report(
            tmp_path,
            selected_variants={"acq:mprage|suffix:t1w"},
        )

        assert len(report) == 1
        assert report[0]["file"].endswith("sub-01_acq-mprage_T1w.json")


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


# ---------------------------------------------------------------------------
# _nibabel_defacing_heuristic — direct implementation tests (lines 224-240)
# ---------------------------------------------------------------------------

class TestNibabelDefacingHeuristicDirect:
    def test_returns_none_on_unreadable_file(self, tmp_path):
        """Lines 239-240: file that can't be opened returns None."""
        from src.mri_json_scrubber import _nibabel_defacing_heuristic
        bad = tmp_path / "not_real.nii"
        bad.write_bytes(b"not a nifti file")
        result = _nibabel_defacing_heuristic(bad)
        assert result is None

    def test_returns_none_on_missing_file(self, tmp_path):
        """Lines 239-240: missing file → exception → returns None."""
        from src.mri_json_scrubber import _nibabel_defacing_heuristic
        result = _nibabel_defacing_heuristic(tmp_path / "missing.nii.gz")
        assert result is None

    def test_returns_false_for_clean_nifti(self, tmp_path):
        """Lines 228-238: real nibabel load of a clean NIfTI returns False."""
        try:
            import nibabel as nib
            import numpy as np
        except ImportError:
            pytest.skip("nibabel not available")

        from src.mri_json_scrubber import _nibabel_defacing_heuristic

        data = np.zeros((4, 4, 4), dtype=np.int16)
        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = tmp_path / "sub-01_T1w.nii.gz"
        nib.save(img, str(nifti_path))

        result = _nibabel_defacing_heuristic(nifti_path)
        assert result is False


# ---------------------------------------------------------------------------
# build_defacing_report — covering lines 335 and 342
# ---------------------------------------------------------------------------

class TestBuildDefacingReportExtra:
    def test_non_anatomical_suffix_json_excluded(self, tmp_path):
        """Line 335: json files whose stem lacks an anat suffix are skipped."""
        sub = tmp_path / "sub-01" / "anat"
        sub.mkdir(parents=True)
        # This JSON has an anat path but not an anat suffix (e.g. _bold)
        json_file = sub / "sub-01_task-rest.json"
        json_file.write_text("{}")
        report = build_defacing_report(tmp_path)
        assert report == []

    def test_anat_json_included_in_report(self, tmp_path):
        """Line 342: result['file'] set relative to project_path."""
        sub = tmp_path / "sub-01" / "anat"
        sub.mkdir(parents=True)
        json_file = sub / "sub-01_T1w.json"
        json_file.write_text("{}")
        report = build_defacing_report(tmp_path)
        assert len(report) == 1
        assert "sub-01" in report[0]["file"]
        assert "T1w" in report[0]["file"]

    def test_build_defacing_report_honors_subject_and_session_exclusions(self, tmp_path):
        anat_a = tmp_path / "sub-01" / "ses-1" / "anat"
        anat_b = tmp_path / "sub-02" / "ses-2" / "anat"
        anat_a.mkdir(parents=True)
        anat_b.mkdir(parents=True)
        (anat_a / "sub-01_ses-1_T1w.json").write_text("{}", encoding="utf-8")
        (anat_b / "sub-02_ses-2_T1w.json").write_text("{}", encoding="utf-8")

        report = build_defacing_report(
            tmp_path,
            excluded_subjects={"sub-02"},
            excluded_sessions={"ses-2"},
        )

        files = {str(entry.get("file") or "") for entry in report}
        assert "sub-01/ses-1/anat/sub-01_ses-1_T1w.json" in files
        assert "sub-02/ses-2/anat/sub-02_ses-2_T1w.json" not in files


class TestDefaceAnatomicalScans:
    def test_returns_error_when_pydeface_missing(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        anat = tmp_path / "sub-001" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-001_T1w.nii.gz").write_bytes(b"nifti")

        monkeypatch.setattr(mri_json_scrubber.shutil, "which", lambda _cmd: None)
        result = deface_anatomical_scans(tmp_path)
        assert result["success"] is False
        assert "pydeface" in str(result.get("error") or "")

    def test_no_anatomical_files_is_success(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        monkeypatch.setattr(mri_json_scrubber.shutil, "which", lambda _cmd: "/usr/bin/pydeface")
        result = deface_anatomical_scans(tmp_path)
        assert result["success"] is True
        assert result["counts"]["total"] == 0

    def test_selected_variants_without_matches_is_success(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        anat = tmp_path / "sub-001" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-001_T1w.nii.gz").write_bytes(b"nifti")

        monkeypatch.setattr(mri_json_scrubber.shutil, "which", lambda _cmd: None)
        result = deface_anatomical_scans(
            tmp_path,
            selected_variants={"acq:mprage|suffix:t1w"},
        )
        assert result["success"] is True
        assert result["counts"]["total"] == 0
        assert "matched the selected defacing filters" in str(result.get("message") or "")

    def test_tracked_dataset_uses_datalad_run(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        anat = tmp_path / "sub-001" / "anat"
        anat.mkdir(parents=True)
        (tmp_path / ".datalad").mkdir(parents=True)
        (anat / "sub-001_T1w.nii.gz").write_bytes(b"nifti")

        def _fake_which(command):
            if command == "pydeface":
                return "/usr/bin/pydeface"
            if command == "datalad":
                return "/usr/bin/datalad"
            if command in {"bet", "fsl"}:
                return "/usr/bin/bet"
            return ""

        monkeypatch.setattr(mri_json_scrubber.shutil, "which", _fake_which)
        monkeypatch.setattr(
            "src.datalad_execution.shutil.which",
            _fake_which,
        )

        seen_commands = []

        def _fake_subprocess_run(
            command,
            cwd=None,
            capture_output=True,
            text=True,
            timeout=None,
            check=False,
            env=None,
        ):
            seen_commands.append([str(item) for item in command])
            if len(command) >= 2 and command[1] == "get":
                return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
            if len(command) >= 2 and command[1] == "run":
                payload = {
                    "counts": {"defaced": 1, "failed": 0},
                    "items": [
                        {
                            "file": "sub-001/anat/sub-001_T1w.nii.gz",
                            "status": "defaced",
                            "message": "Defacing completed",
                        }
                    ],
                }
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"run log\n{json.dumps(payload)}\n",
                    stderr="",
                )
            raise AssertionError(f"Unexpected command: {command}")

        monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_subprocess_run)

        result = deface_anatomical_scans(tmp_path, force=True)
        assert result["success"] is True
        assert result["counts"]["defaced"] == 1
        assert result["datalad"]["used_run"] is True
        assert any(command[0:2] == ["/usr/bin/datalad", "get"] for command in seen_commands)
        assert any(command[0:2] == ["/usr/bin/datalad", "run"] for command in seen_commands)

    def test_tracked_dataset_defacing_runs_once_per_subject(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        anat_a = tmp_path / "sub-001" / "anat"
        anat_b = tmp_path / "sub-002" / "anat"
        anat_a.mkdir(parents=True)
        anat_b.mkdir(parents=True)
        (tmp_path / ".datalad").mkdir(parents=True)
        (anat_a / "sub-001_T1w.nii.gz").write_bytes(b"nifti")
        (anat_b / "sub-002_T1w.nii.gz").write_bytes(b"nifti")

        def _fake_which(command):
            if command == "pydeface":
                return "/usr/bin/pydeface"
            if command == "datalad":
                return "/usr/bin/datalad"
            if command in {"bet", "fsl"}:
                return "/usr/bin/bet"
            return ""

        monkeypatch.setattr(mri_json_scrubber.shutil, "which", _fake_which)
        monkeypatch.setattr("src.datalad_execution.shutil.which", _fake_which)

        seen_commands: list[list[str]] = []

        def _fake_subprocess_run(
            command,
            cwd=None,
            capture_output=True,
            text=True,
            timeout=None,
            check=False,
            env=None,
        ):
            command_as_text = [str(item) for item in command]
            seen_commands.append(command_as_text)
            if len(command) >= 2 and command[1] == "get":
                return SimpleNamespace(returncode=0, stdout="get ok", stderr="")
            if len(command) >= 2 and command[1] == "run":
                subject = "sub-001" if "sub-001" in " ".join(command_as_text) else "sub-002"
                payload = {
                    "counts": {"defaced": 1, "failed": 0},
                    "items": [
                        {
                            "file": f"{subject}/anat/{subject}_T1w.nii.gz",
                            "status": "defaced",
                            "message": "Defacing completed",
                        }
                    ],
                }
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"run log\n{json.dumps(payload)}\n",
                    stderr="",
                )
            raise AssertionError(f"Unexpected command: {command}")

        monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_subprocess_run)

        result = deface_anatomical_scans(tmp_path, force=True)
        assert result["success"] is True
        assert result["counts"]["defaced"] == 2
        datalad = result.get("datalad") or {}
        assert datalad.get("used_run") is True
        assert datalad.get("run_count") == 2
        assert len(datalad.get("groups") or []) == 2
        run_commands = [command for command in seen_commands if command[1] == "run"]
        assert len(run_commands) == 2


class TestDefacingPreflight:
    def test_has_anatomical_data_true_with_anat_nifti(self, tmp_path):
        anat = tmp_path / "sub-001" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-001_T1w.nii.gz").write_bytes(b"nifti")
        assert has_anatomical_data(tmp_path) is True

    def test_preflight_hides_defacing_when_no_anat(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        monkeypatch.setattr(
            mri_json_scrubber.shutil,
            "which",
            lambda cmd: "/usr/bin/pydeface" if cmd == "pydeface" else "/usr/bin/bet",
        )
        preflight = get_defacing_preflight(tmp_path)
        assert preflight["has_anatomical_data"] is False
        assert preflight["can_run_defacing"] is False

    def test_preflight_requires_fsl_even_when_pydeface_exists(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        anat = tmp_path / "sub-001" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-001_T1w.nii.gz").write_bytes(b"nifti")

        monkeypatch.setattr(
            mri_json_scrubber.shutil,
            "which",
            lambda cmd: "/usr/bin/pydeface" if cmd == "pydeface" else "",
        )
        preflight = get_defacing_preflight(tmp_path)
        assert preflight["pydeface_available"] is True
        assert preflight["fsl_available"] is False
        assert preflight["can_run_defacing"] is False

    def test_preflight_includes_available_scan_variants(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        anat = tmp_path / "sub-001" / "anat"
        anat.mkdir(parents=True)
        (anat / "sub-001_acq-mprage_T1w.nii.gz").write_bytes(b"nifti")
        (anat / "sub-001_T2w.nii.gz").write_bytes(b"nifti")

        monkeypatch.setattr(
            mri_json_scrubber.shutil,
            "which",
            lambda cmd: "/usr/bin/pydeface" if cmd == "pydeface" else "/usr/bin/bet",
        )
        preflight = get_defacing_preflight(tmp_path)

        variants = preflight.get("available_scan_variants") or []
        variant_keys = {str(entry.get("key") or "") for entry in variants}
        assert "acq:mprage|suffix:t1w" in variant_keys
        assert "suffix:t2w" in variant_keys


class TestDefacingExportCopy:
    def test_prepare_defacing_export_copy_preserves_relative_structure(self, tmp_path):
        project_path = tmp_path / "study"
        anat_dir = project_path / "sub-001" / "ses-1" / "anat"
        func_dir = project_path / "sub-001" / "ses-1" / "func"
        anat_dir.mkdir(parents=True)
        func_dir.mkdir(parents=True)

        source_nifti = anat_dir / "sub-001_ses-1_acq-mprage_T1w.nii.gz"
        source_json = anat_dir / "sub-001_ses-1_acq-mprage_T1w.json"
        non_anat_file = func_dir / "sub-001_ses-1_task-rest_bold.nii.gz"

        source_nifti.write_bytes(b"nifti")
        source_json.write_text("{}", encoding="utf-8")
        non_anat_file.write_bytes(b"bold")

        output_root = tmp_path / "exports"
        result = prepare_defacing_export_copy(project_path, output_root)

        assert result.get("success") is True
        target_path = Path(str(result.get("target_path") or ""))
        assert target_path.exists()
        assert (target_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_acq-mprage_T1w.nii.gz").exists()
        assert (target_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_acq-mprage_T1w.json").exists()
        assert not (target_path / "sub-001" / "ses-1" / "func" / "sub-001_ses-1_task-rest_bold.nii.gz").exists()

    def test_prepare_defacing_export_copy_honors_selected_variants(self, tmp_path):
        project_path = tmp_path / "study"
        anat_dir = project_path / "sub-001" / "anat"
        anat_dir.mkdir(parents=True)

        mprage_nifti = anat_dir / "sub-001_acq-mprage_T1w.nii.gz"
        t2w_nifti = anat_dir / "sub-001_T2w.nii.gz"
        mprage_nifti.write_bytes(b"mprage")
        t2w_nifti.write_bytes(b"t2w")

        output_root = tmp_path / "exports"
        result = prepare_defacing_export_copy(
            project_path,
            output_root,
            selected_variants={"acq:mprage|suffix:t1w"},
        )

        assert result.get("success") is True
        target_path = Path(str(result.get("target_path") or ""))
        assert (target_path / "sub-001" / "anat" / "sub-001_acq-mprage_T1w.nii.gz").exists()
        assert not (target_path / "sub-001" / "anat" / "sub-001_T2w.nii.gz").exists()

    def test_prepare_defacing_export_copy_honors_subject_and_session_exclusions(self, tmp_path):
        project_path = tmp_path / "study"
        anat_a = project_path / "sub-001" / "ses-1" / "anat"
        anat_b = project_path / "sub-002" / "ses-2" / "anat"
        anat_a.mkdir(parents=True)
        anat_b.mkdir(parents=True)

        (anat_a / "sub-001_ses-1_T1w.nii.gz").write_bytes(b"a")
        (anat_b / "sub-002_ses-2_T1w.nii.gz").write_bytes(b"b")

        output_root = tmp_path / "exports"
        result = prepare_defacing_export_copy(
            project_path,
            output_root,
            excluded_subjects={"sub-002"},
            excluded_sessions={"ses-2"},
        )

        assert result.get("success") is True
        target_path = Path(str(result.get("target_path") or ""))
        assert (target_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T1w.nii.gz").exists()
        assert not (target_path / "sub-002" / "ses-2" / "anat" / "sub-002_ses-2_T1w.nii.gz").exists()

    def test_prepare_defacing_export_copy_can_clone_datalad_dataset(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        project_path = tmp_path / "study"
        anat_dir = project_path / "sub-001" / "anat"
        anat_dir.mkdir(parents=True)
        (project_path / ".datalad").mkdir(parents=True)
        (anat_dir / "sub-001_T1w.nii.gz").write_bytes(b"nifti")

        seen_commands = []

        def _fake_subprocess_run(
            command,
            capture_output=True,
            text=True,
            timeout=None,
            check=False,
        ):
            seen_commands.append([str(item) for item in command])
            destination = Path(str(command[3]))
            shutil.copytree(project_path, destination)
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(mri_json_scrubber, "resolve_datalad_executable", lambda: "/usr/bin/datalad")
        monkeypatch.setattr(mri_json_scrubber.subprocess, "run", _fake_subprocess_run)

        output_root = tmp_path / "exports"
        result = prepare_defacing_export_copy(
            project_path,
            output_root,
            preserve_datalad_metadata=True,
        )

        assert result.get("success") is True
        target_path = Path(str(result.get("target_path") or ""))
        assert (target_path / ".datalad").exists()
        assert (target_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz").exists()
        assert any(command[0:2] == ["/usr/bin/datalad", "clone"] for command in seen_commands)

    def test_prepare_defacing_export_copy_fails_without_datalad_executable(self, tmp_path, monkeypatch):
        from src import mri_json_scrubber

        project_path = tmp_path / "study"
        anat_dir = project_path / "sub-001" / "anat"
        anat_dir.mkdir(parents=True)
        (project_path / ".datalad").mkdir(parents=True)
        (anat_dir / "sub-001_T1w.nii.gz").write_bytes(b"nifti")

        monkeypatch.setattr(mri_json_scrubber, "resolve_datalad_executable", lambda: "")

        result = prepare_defacing_export_copy(
            project_path,
            tmp_path / "exports",
            preserve_datalad_metadata=True,
        )

        assert result.get("success") is False
        assert "requires datalad" in str(result.get("error") or "").lower()
