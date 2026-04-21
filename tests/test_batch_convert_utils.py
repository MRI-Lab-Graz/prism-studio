"""Tests for src/batch_convert.py — pure utility functions."""

import sys
import os
import pytest
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from src.batch_convert import (
    parse_bids_filename,
    detect_modality,
    _files_identical,
    safe_write_file,
    BatchConvertResult,
    ConvertedFile,
    _downsample_xy,
    _line_svg,
    _hist_svg,
    _create_physio_sidecar,
    _create_eyetracking_sidecar,
    _find_physio_sidecar,
)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ---------------------------------------------------------------------------
# parse_bids_filename
# ---------------------------------------------------------------------------

class TestParseBidsFilename:
    def test_full_bids_name(self):
        result = parse_bids_filename("sub-003_ses-1_task-rest.raw")
        assert result is not None
        assert result["sub"] == "sub-003"
        assert result["ses"] == "ses-1"
        assert result["task"] == "task-rest"
        assert result["ext"] == "raw"

    def test_no_session(self):
        result = parse_bids_filename("sub-001_task-gaze.edf")
        assert result is not None
        assert result["sub"] == "sub-001"
        assert result["ses"] is None
        assert result["task"] == "task-gaze"

    def test_invalid_returns_none(self):
        assert parse_bids_filename("notabidsfile.txt") is None
        assert parse_bids_filename("") is None

    def test_extra_entities(self):
        result = parse_bids_filename("sub-01_ses-1_task-rest_run-01.edf")
        assert result is not None
        assert "run-01" in result["extra"]

    def test_extension_lowercased(self):
        result = parse_bids_filename("sub-001_task-foo.RAW")
        assert result is not None
        assert result["ext"] == "raw"


# ---------------------------------------------------------------------------
# detect_modality
# ---------------------------------------------------------------------------

class TestDetectModality:
    def test_physio_raw(self):
        assert detect_modality(".raw") == "physio"

    def test_physio_vpd(self):
        assert detect_modality(".vpd") == "physio"

    def test_generic_tsv(self):
        assert detect_modality(".tsv") == "generic"

    def test_generic_csv(self):
        assert detect_modality(".csv") == "generic"

    def test_unknown_returns_none(self):
        assert detect_modality(".xyz") is None

    def test_without_dot(self):
        assert detect_modality("raw") == "physio"

    def test_case_insensitive(self):
        assert detect_modality(".TSV") == "generic"


# ---------------------------------------------------------------------------
# _files_identical
# ---------------------------------------------------------------------------

class TestFilesIdentical:
    def test_identical_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello world")
        f2.write_bytes(b"hello world")
        assert _files_identical(f1, f2) is True

    def test_different_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello")
        f2.write_bytes(b"world")
        assert _files_identical(f1, f2) is False

    def test_missing_file_returns_false(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_bytes(b"hello")
        assert _files_identical(f1, tmp_path / "missing.txt") is False


# ---------------------------------------------------------------------------
# safe_write_file
# ---------------------------------------------------------------------------

class TestSafeWriteFile:
    def test_writes_new_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_bytes(b"content")
        dst = tmp_path / "subdir" / "dst.txt"
        success, reason = safe_write_file(src, dst)
        assert success is True
        assert reason is None
        assert dst.read_bytes() == b"content"

    def test_identical_file_skipped(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_bytes(b"content")
        dst = tmp_path / "dst.txt"
        dst.write_bytes(b"content")
        success, reason = safe_write_file(src, dst)
        assert success is False
        assert reason == "identical"

    def test_different_file_conflict(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_bytes(b"new content")
        dst = tmp_path / "dst.txt"
        dst.write_bytes(b"old content")
        success, reason = safe_write_file(src, dst, allow_overwrite=False)
        assert success is False
        assert reason == "different"

    def test_overwrite_allowed(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_bytes(b"new content")
        dst = tmp_path / "dst.txt"
        dst.write_bytes(b"old content")
        success, reason = safe_write_file(src, dst, allow_overwrite=True)
        assert success is True
        assert dst.read_bytes() == b"new content"

    def test_missing_source_returns_false(self, tmp_path):
        dst = tmp_path / "dst.txt"
        success, reason = safe_write_file(tmp_path / "missing.txt", dst)
        assert success is False
        assert reason is None


# ---------------------------------------------------------------------------
# BatchConvertResult
# ---------------------------------------------------------------------------

class TestBatchConvertResult:
    def _make_converted(self, success: bool) -> "ConvertedFile":
        return ConvertedFile(
            source_path=Path("x"),
            output_files=[],
            modality="physio",
            subject="sub-001",
            session=None,
            task="task-rest",
            success=success,
        )

    def test_success_count(self, tmp_path):
        result = BatchConvertResult(source_folder=tmp_path, output_folder=tmp_path)
        result.converted = [
            self._make_converted(True),
            self._make_converted(True),
            self._make_converted(False),
        ]
        assert result.success_count == 2

    def test_error_count(self, tmp_path):
        result = BatchConvertResult(source_folder=tmp_path, output_folder=tmp_path)
        result.converted = [
            self._make_converted(True),
            self._make_converted(False),
            self._make_converted(False),
        ]
        assert result.error_count == 2


# ---------------------------------------------------------------------------
# _downsample_xy
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")
class TestDownsampleXY:
    def test_short_array_unchanged(self):
        x = np.arange(100)
        y = np.arange(100)
        xd, yd = _downsample_xy(x, y, max_points=1400)
        assert len(xd) == 100

    def test_long_array_downsampled(self):
        x = np.arange(10000)
        y = np.arange(10000)
        xd, yd = _downsample_xy(x, y, max_points=1000)
        assert len(xd) <= 1000

    def test_preserves_endpoints(self):
        x = np.arange(5000)
        y = np.ones(5000)
        xd, yd = _downsample_xy(x, y, max_points=100)
        assert xd[0] == 0  # first element preserved


# ---------------------------------------------------------------------------
# _line_svg
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")
class TestLineSvg:
    def test_empty_array_returns_placeholder(self):
        result = _line_svg(np.array([]), np.array([]))
        assert "Not enough data" in result or "<div" in result

    def test_returns_svg_string(self):
        x = np.linspace(0, 10, 50)
        y = np.sin(x)
        result = _line_svg(x, y, title="ECG")
        assert "<svg" in result or "svg" in result.lower() or "polyline" in result

    def test_title_in_output(self):
        x = np.arange(10)
        y = np.arange(10, dtype=float)
        result = _line_svg(x, y, title="Test Signal")
        assert "Test Signal" in result


# ---------------------------------------------------------------------------
# _hist_svg
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")
class TestHistSvg:
    def test_empty_array(self):
        result = _hist_svg(np.array([]))
        assert isinstance(result, str)

    def test_normal_data(self):
        data = np.array([1.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0])
        result = _hist_svg(data)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _create_physio_sidecar
# ---------------------------------------------------------------------------

import json as _json


class TestCreatePhysioSidecar:
    def test_creates_json_file(self, tmp_path):
        src = tmp_path / "sub-01_task-rest.raw"
        src.write_bytes(b"data")
        out = tmp_path / "sidecar.json"
        _create_physio_sidecar(src, out, task_name="task-rest")
        assert out.exists()
        data = _json.loads(out.read_text())
        assert "Technical" in data
        assert "Channels" in data

    def test_task_name_stored(self, tmp_path):
        src = tmp_path / "file.raw"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="task-faces")
        data = _json.loads(out.read_text())
        assert data["Study"]["TaskName"] == "faces"

    def test_sampling_frequency_stored(self, tmp_path):
        src = tmp_path / "file.raw"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="rest", sampling_rate=1000.0)
        data = _json.loads(out.read_text())
        assert data["Technical"]["SamplingFrequency"] == 1000.0

    def test_custom_channels(self, tmp_path):
        src = tmp_path / "file.raw"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="rest",
                                extra_meta={"Channels": ["ECG", "RESP"]})
        data = _json.loads(out.read_text())
        assert "ECG" in data["Channels"]
        assert data["Channels"]["ECG"]["Type"] == "ECG"
        assert data["Channels"]["RESP"]["Type"] == "RESP"

    def test_default_channel_fallback(self, tmp_path):
        src = tmp_path / "file.raw"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="rest")
        data = _json.loads(out.read_text())
        assert "signal" in data["Channels"]

    def test_recording_duration_added(self, tmp_path):
        src = tmp_path / "file.raw"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="rest",
                                extra_meta={"RecordingDuration": 120.5})
        data = _json.loads(out.read_text())
        assert data.get("Acquisition", {}).get("AcquisitionDuration") == 120.5

    def test_edf_source_detected(self, tmp_path):
        src = tmp_path / "file.edf"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="rest")
        data = _json.loads(out.read_text())
        assert data["Metadata"]["ConvertedFrom"] == "EDF"

    def test_channel_type_inference(self, tmp_path):
        src = tmp_path / "file.raw"
        src.write_bytes(b"x")
        out = tmp_path / "s.json"
        _create_physio_sidecar(src, out, task_name="rest",
                                extra_meta={"Channels": ["eda_signal", "ppg_ch", "marker_1"]})
        data = _json.loads(out.read_text())
        assert data["Channels"]["eda_signal"]["Type"] == "EDA"
        assert data["Channels"]["ppg_ch"]["Type"] == "PPG"
        assert data["Channels"]["marker_1"]["Type"] == "TRIGGER"


# ---------------------------------------------------------------------------
# _create_eyetracking_sidecar
# ---------------------------------------------------------------------------

class TestCreateEyetrackingSidecar:
    def test_creates_json_file(self, tmp_path):
        src = tmp_path / "file.edf"
        src.write_bytes(b"data")
        out = tmp_path / "et.json"
        _create_eyetracking_sidecar(src, out, task_name="task-gaze")
        assert out.exists()
        data = _json.loads(out.read_text())
        assert "Technical" in data

    def test_task_name_stored(self, tmp_path):
        src = tmp_path / "file.edf"
        src.write_bytes(b"x")
        out = tmp_path / "et.json"
        _create_eyetracking_sidecar(src, out, task_name="task-gaze")
        data = _json.loads(out.read_text())
        assert data["Study"]["TaskName"] == "gaze"

    def test_sampling_rate_from_extra_meta(self, tmp_path):
        src = tmp_path / "file.edf"
        src.write_bytes(b"x")
        out = tmp_path / "et.json"
        _create_eyetracking_sidecar(src, out, task_name="gaze",
                                     extra_meta={"SamplingFrequency": 500})
        data = _json.loads(out.read_text())
        assert data["Technical"]["SamplingRate"] == 500


# ---------------------------------------------------------------------------
# _find_physio_sidecar
# ---------------------------------------------------------------------------

class TestFindPhysioSidecar:
    def test_finds_local_json(self, tmp_path):
        edf = tmp_path / "sub-01_task-rest.edf"
        edf.write_bytes(b"x")
        local = tmp_path / "sub-01_task-rest.json"
        local.write_text("{}")
        result = _find_physio_sidecar(tmp_path, "task-rest", edf)
        assert result == local

    def test_finds_root_sidecar(self, tmp_path):
        edf = tmp_path / "sub-01" / "sub-01_task-rest.edf"
        edf.parent.mkdir()
        edf.write_bytes(b"x")
        root = tmp_path / "task-rest_physio.json"
        root.write_text("{}")
        result = _find_physio_sidecar(tmp_path, "task-rest", edf)
        assert result == root

    def test_returns_none_when_missing(self, tmp_path):
        edf = tmp_path / "sub-01_task-rest.edf"
        edf.write_bytes(b"x")
        result = _find_physio_sidecar(tmp_path, "task-rest", edf)
        assert result is None

    def test_task_prefix_stripped(self, tmp_path):
        edf = tmp_path / "sub-01_task-faces.edf"
        edf.write_bytes(b"x")
        root = tmp_path / "task-faces_physio.json"
        root.write_text("{}")
        result = _find_physio_sidecar(tmp_path, "task-faces", edf)
        assert result == root
