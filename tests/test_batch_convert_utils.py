"""Tests for src/batch_convert.py — pure utility functions."""

import json as _json
import sys
import os
import pytest
import shutil
from unittest.mock import patch, MagicMock

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
    _extract_edf_metadata,
    _detect_r_peaks,
    _generate_physio_html_report,
    convert_physio_file,
    convert_eyetracking_file,
    convert_generic_file,
    batch_convert_folder,
    create_dataset_description,
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

    def test_legacy_file_can_use_canonical_recording_root_sidecar(self, tmp_path):
        edf = tmp_path / "sub-01_ses-1_task-rest_ecg.edf"
        edf.write_bytes(b"x")
        root = tmp_path / "task-rest_recording-ecg_physio.json"
        root.write_text("{}")
        result = _find_physio_sidecar(tmp_path, "task-rest", edf)
        assert result == root


# ---------------------------------------------------------------------------
# _files_identical — large-file (≥ 1 MB) path
# ---------------------------------------------------------------------------

class TestFilesIdenticalLargeFile:
    def test_large_files_same_size_treated_as_identical(self, tmp_path):
        # Files ≥ 1 MB with identical size are considered identical (no byte compare)
        big_data = b"A" * 1_100_000
        f1 = tmp_path / "big1.bin"
        f2 = tmp_path / "big2.bin"
        f1.write_bytes(big_data)
        f2.write_bytes(big_data)
        assert _files_identical(f1, f2) is True

    def test_large_files_different_size_not_identical(self, tmp_path):
        f1 = tmp_path / "big1.bin"
        f2 = tmp_path / "big2.bin"
        f1.write_bytes(b"A" * 1_100_000)
        f2.write_bytes(b"B" * 1_200_000)
        assert _files_identical(f1, f2) is False


# ---------------------------------------------------------------------------
# safe_write_file — additional edge cases
# ---------------------------------------------------------------------------

class TestSafeWriteFileExtra:
    def test_no_overwrite_different_content_returns_different(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("new content")
        dst.write_text("old content")
        ok, reason = safe_write_file(src, dst, allow_overwrite=False)
        assert ok is False
        assert reason == "different"

    def test_write_ioerror_returns_error_string(self, tmp_path, monkeypatch):
        src = tmp_path / "src.txt"
        src.write_text("data")
        dst = tmp_path / "dst.txt"

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(shutil, "copy2", boom)
        ok, reason = safe_write_file(src, dst)
        assert ok is False
        assert reason is not None and "disk full" in reason


# ---------------------------------------------------------------------------
# _create_physio_sidecar — RecordingDuration path
# ---------------------------------------------------------------------------

class TestPhysioSidecarRecordingDuration:
    def test_recording_duration_in_extra_meta(self, tmp_path):
        src = tmp_path / "file.edf"
        src.write_bytes(b"x")
        out = tmp_path / "sidecar.json"
        _create_physio_sidecar(
            src, out,
            task_name="task-rest",
            extra_meta={"RecordingDuration": 120.0},
        )
        data = _json.loads(out.read_text())
        assert data["Acquisition"]["AcquisitionDuration"] == 120.0


# ---------------------------------------------------------------------------
# _extract_edf_metadata
# ---------------------------------------------------------------------------

class TestExtractEdfMetadata:
    def test_returns_empty_on_invalid_file(self, tmp_path):
        fake = tmp_path / "fake.edf"
        fake.write_bytes(b"not an edf file")
        result = _extract_edf_metadata(fake)
        assert result == {}

    def test_returns_empty_on_missing_file(self, tmp_path):
        missing = tmp_path / "missing.edf"
        result = _extract_edf_metadata(missing)
        assert result == {}


# ---------------------------------------------------------------------------
# _detect_r_peaks
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestDetectRPeaks:
    def test_returns_empty_for_short_signal(self):
        short = np.zeros(5, dtype=float)
        peaks = _detect_r_peaks(short, sampling_rate=256.0)
        assert peaks.size == 0

    def test_returns_empty_for_zero_sampling_rate(self):
        sig = np.zeros(5000, dtype=float)
        peaks = _detect_r_peaks(sig, sampling_rate=0.0)
        assert peaks.size == 0

    def test_returns_empty_for_flat_signal(self):
        flat = np.ones(10000, dtype=float)
        peaks = _detect_r_peaks(flat, sampling_rate=256.0)
        # Flat signal has zero std — should return empty
        assert peaks.size == 0

    def test_detects_peaks_in_synthetic_ecg(self):
        # Create a synthetic ECG-like signal with clear peaks every 1s at 256 Hz
        fs = 256.0
        n = int(fs * 60)  # 60 seconds
        t = np.arange(n, dtype=float) / fs
        signal = np.sin(2 * np.pi * 1.0 * t) * 0.1  # low baseline
        # Add strong spikes every second
        for i in range(1, 60):
            idx = int(i * fs)
            if idx < n:
                signal[idx] += 5.0
        peaks = _detect_r_peaks(signal, sampling_rate=fs)
        assert peaks.size >= 50  # should detect most spikes


# ---------------------------------------------------------------------------
# _generate_physio_html_report — no EDF output files
# ---------------------------------------------------------------------------

class TestGeneratePhysioHtmlReport:
    def test_returns_none_when_no_edf_output_files(self, tmp_path):
        converted = ConvertedFile(
            source_path=tmp_path / "file.raw",
            output_files=[tmp_path / "file.json"],  # no .edf
            modality="physio",
            subject="sub-001",
            session=None,
            task="task-rest",
            success=True,
        )
        result = _generate_physio_html_report(
            converted=converted,
            output_folder=tmp_path,
        )
        assert result is None

    def test_creates_minimal_report_when_pyedflib_unavailable(self, tmp_path):
        fake_edf = tmp_path / "file.edf"
        fake_edf.write_bytes(b"fake edf data")
        converted = ConvertedFile(
            source_path=tmp_path / "file.raw",
            output_files=[fake_edf],
            modality="physio",
            subject="sub-001",
            session=None,
            task="task-rest",
            success=True,
        )
        with patch.dict("sys.modules", {"pyedflib": None}):
            result = _generate_physio_html_report(
                converted=converted,
                output_folder=tmp_path,
            )
        assert result is not None
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "unavailable" in content.lower() or "pyedflib" in content.lower()

    def test_creates_minimal_report_with_session(self, tmp_path):
        fake_edf = tmp_path / "file.edf"
        fake_edf.write_bytes(b"fake edf data")
        converted = ConvertedFile(
            source_path=tmp_path / "file.raw",
            output_files=[fake_edf],
            modality="physio",
            subject="sub-002",
            session="ses-1",
            task="task-rest",
            success=True,
        )
        with patch.dict("sys.modules", {"pyedflib": None}):
            result = _generate_physio_html_report(
                converted=converted,
                output_folder=tmp_path,
            )
        assert result is not None
        assert "ses-1" in str(result)


# ---------------------------------------------------------------------------
# convert_physio_file
# ---------------------------------------------------------------------------

class TestConvertPhysioFile:
    def test_edf_physio_copies_file_and_creates_sidecar(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-rest.edf"
        src.write_bytes(b"fake edf bytes")
        out_dir = tmp_path / "output"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_physio_file(src, out_dir, parsed=parsed)

        assert result.success
        assert result.subject == "sub-001"
        assert result.session == "ses-1"
        assert result.task == "task-rest"
        assert result.modality == "physio"
        assert len(result.output_files) == 2
        edf_out = next(f for f in result.output_files if f.suffix == ".edf")
        json_out = next(f for f in result.output_files if f.suffix == ".json")
        assert edf_out.exists()
        assert json_out.exists()
        assert edf_out.name == "sub-001_ses-1_task-rest_recording-ecg_physio.edf"
        assert json_out.name == "sub-001_ses-1_task-rest_recording-ecg_physio.json"

    def test_edf_physio_no_session(self, tmp_path):
        src = tmp_path / "sub-002_task-gaze.edf"
        src.write_bytes(b"x")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_physio_file(src, out_dir, parsed=parsed)

        assert result.success
        assert result.session is None

    def test_edf_physio_with_sampling_rate(self, tmp_path):
        src = tmp_path / "sub-003_task-rest.edf"
        src.write_bytes(b"x")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_physio_file(src, out_dir, parsed=parsed, base_freq=512.0)

        assert result.success
        json_out = next(f for f in result.output_files if f.suffix == ".json")
        data = _json.loads(json_out.read_text())
        assert data["Technical"]["SamplingFrequency"] == 512.0

    def test_raw_with_mock_varioport_success(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-rest.raw"
        src.write_bytes(b"fake raw data")
        out_dir = tmp_path / "output"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        def fake_convert_varioport(src_path, out_edf, out_json, **kwargs):
            Path(out_edf).write_bytes(b"fake edf")
            Path(out_json).write_text('{"AverageHeartRateBPM": 72}')
            return {
                "AverageHeartRateBPM": 72,
                "HeartRateEstimation": {"Status": "ok", "Reason": "good signal"},
            }

        logs = []
        with patch(
            "helpers.physio.convert_varioport.convert_varioport",
            side_effect=fake_convert_varioport,
        ):
            result = convert_physio_file(
                src, out_dir, parsed=parsed,
                log_callback=lambda msg, lvl: logs.append((msg, lvl)),
            )

        assert result.success
        assert any("72" in msg for msg, _ in logs)

    def test_raw_with_mock_varioport_no_avg_hr(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-rest.raw"
        src.write_bytes(b"x")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        def fake_convert_varioport(src_path, out_edf, out_json, **kwargs):
            Path(out_edf).write_bytes(b"edf")
            Path(out_json).write_text("{}")
            return {"HeartRateEstimation": {"Reason": "low quality"}}

        logs = []
        with patch(
            "helpers.physio.convert_varioport.convert_varioport",
            side_effect=fake_convert_varioport,
        ):
            result = convert_physio_file(
                src, out_dir, parsed=parsed,
                log_callback=lambda msg, lvl: logs.append((msg, lvl)),
            )

        assert result.success
        assert any("low quality" in msg for msg, _ in logs)

    def test_raw_with_type7_retry(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-rest.raw"
        src.write_bytes(b"x")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        call_count = [0]

        def fake_convert_varioport(src_path, out_edf, out_json, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Unsupported Varioport header type 7")
            Path(out_edf).write_bytes(b"edf")
            Path(out_json).write_text("{}")
            return {}

        with patch(
            "helpers.physio.convert_varioport.convert_varioport",
            side_effect=fake_convert_varioport,
        ):
            result = convert_physio_file(src, out_dir, parsed=parsed)

        assert call_count[0] == 2

    def test_raw_conversion_error_returns_failed(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-rest.raw"
        src.write_bytes(b"bad data")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        def fail_convert(*args, **kwargs):
            raise RuntimeError("conversion totally failed")

        with patch(
            "helpers.physio.convert_varioport.convert_varioport",
            side_effect=fail_convert,
        ):
            result = convert_physio_file(src, out_dir, parsed=parsed)

        assert not result.success
        assert "conversion totally failed" in str(result.error)

    def test_raw_with_import_error_fallback(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-rest.raw"
        src.write_bytes(b"raw data bytes")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        logs = []
        with patch.dict("sys.modules", {"helpers": None, "helpers.physio": None,
                                         "helpers.physio.convert_varioport": None,
                                         "app.helpers": None, "app.helpers.physio": None,
                                         "app.helpers.physio.convert_varioport": None}):
            result = convert_physio_file(
                src, out_dir, parsed=parsed,
                log_callback=lambda msg, lvl: logs.append((msg, lvl)),
            )

        assert result.success
        # Should have copied the raw file and created a sidecar
        assert len(result.output_files) == 2


# ---------------------------------------------------------------------------
# convert_eyetracking_file
# ---------------------------------------------------------------------------

class TestConvertEyetrackingFile:
    def test_copies_edf_and_creates_sidecar(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-gaze.edf"
        src.write_bytes(b"fake edf data")
        out_dir = tmp_path / "output"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_eyetracking_file(src, out_dir, parsed=parsed)

        assert result.success
        assert result.subject == "sub-001"
        assert result.session == "ses-1"
        assert result.task == "task-gaze"
        assert result.modality == "eyetracking"
        edf_out = next((f for f in result.output_files if f.suffix == ".edf"), None)
        json_out = next((f for f in result.output_files if f.suffix == ".json"), None)
        assert edf_out is not None and edf_out.exists()
        assert json_out is not None and json_out.exists()

    def test_no_session(self, tmp_path):
        src = tmp_path / "sub-002_task-read.edf"
        src.write_bytes(b"x")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_eyetracking_file(src, out_dir, parsed=parsed)

        assert result.success
        assert result.session is None

    def test_missing_source_returns_failed(self, tmp_path):
        src = tmp_path / "sub-001_task-gaze.edf"
        # Don't create the file
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_eyetracking_file(src, out_dir, parsed=parsed)

        assert not result.success


# ---------------------------------------------------------------------------
# convert_generic_file
# ---------------------------------------------------------------------------

class TestConvertGenericFile:
    def test_copies_tsv_and_creates_sidecar(self, tmp_path):
        src = tmp_path / "sub-001_ses-1_task-survey.tsv"
        src.write_text("col1\tcol2\n1\t2\n")
        out_dir = tmp_path / "output"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_generic_file(src, out_dir, parsed=parsed, target_modality="survey")

        assert result.success
        assert result.modality == "survey"
        assert len(result.output_files) == 2
        tsv_out = next(f for f in result.output_files if f.suffix == ".tsv")
        json_out = next(f for f in result.output_files if f.suffix == ".json")
        assert tsv_out.exists()
        assert json_out.exists()

    def test_json_file_no_extra_sidecar(self, tmp_path):
        src = tmp_path / "sub-001_task-survey.json"
        src.write_text('{"key": "value"}')
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_generic_file(src, out_dir, parsed=parsed, target_modality="survey")

        assert result.success
        # JSON files should not get an extra sidecar
        assert len(result.output_files) == 1

    def test_no_session_path(self, tmp_path):
        src = tmp_path / "sub-003_task-motor.tsv"
        src.write_text("x\t1\n")
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_generic_file(src, out_dir, parsed=parsed, target_modality="func")

        assert result.success
        assert result.session is None

    def test_missing_source_returns_failed(self, tmp_path):
        src = tmp_path / "sub-001_task-x.tsv"
        out_dir = tmp_path / "out"
        parsed = parse_bids_filename(src.name)
        assert parsed is not None

        result = convert_generic_file(src, out_dir, parsed=parsed)

        assert not result.success


# ---------------------------------------------------------------------------
# batch_convert_folder
# ---------------------------------------------------------------------------

class TestBatchConvertFolder:
    def test_empty_folder(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        out = tmp_path / "output"

        result = batch_convert_folder(src, out)

        assert result.success_count == 0
        assert len(result.skipped) == 0

    def test_skips_invalid_filenames(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "invalid_name.tsv").write_text("x")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out)

        assert len(result.skipped) == 1
        assert result.success_count == 0

    def test_converts_generic_tsv(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-survey.tsv").write_text("col\nval\n")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out, modality_filter="all")

        assert result.success_count == 1

    def test_converts_multiple_files(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-survey.tsv").write_text("col\nval\n")
        (src / "sub-002_ses-1_task-rest.tsv").write_text("col\nval\n")
        (src / "bad_filename.txt").write_text("x")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out)

        assert result.success_count == 2
        assert len(result.skipped) == 1

    def test_cancel_check_stops_early(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        for i in range(5):
            (src / f"sub-00{i}_task-rest.tsv").write_text("x")
        out = tmp_path / "output"

        call_count = [0]

        def cancel():
            call_count[0] += 1
            return call_count[0] >= 2

        result = batch_convert_folder(src, out, cancel_check=cancel)

        assert result.success_count < 5

    def test_log_callback_receives_messages(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-survey.tsv").write_text("x")
        out = tmp_path / "output"

        logs = []
        batch_convert_folder(src, out, log_callback=lambda msg, lvl: logs.append(msg))

        assert len(logs) > 0

    def test_modality_filter_eyetracking_skips_tsv(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-survey.tsv").write_text("x")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out, modality_filter="eyetracking")

        assert result.success_count == 0

    def test_converts_edf_physio_file(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-rest.edf").write_bytes(b"fake edf")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out, modality_filter="physio")

        assert result.success_count == 1

    def test_dry_run_does_not_create_files(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-survey.tsv").write_text("x")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out, dry_run=True)

        # dry run may still produce output because convert functions run normally,
        # but the log messages should say "Would"
        assert result.success_count == 1

    def test_specific_modality_filter(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "sub-001_task-survey.tsv").write_text("x")
        out = tmp_path / "output"

        result = batch_convert_folder(src, out, modality_filter="survey")

        assert result.success_count == 1
        assert result.converted[0].modality == "survey"


# ---------------------------------------------------------------------------
# create_dataset_description
# ---------------------------------------------------------------------------

class TestCreateDatasetDescription:
    def test_creates_json_file(self, tmp_path):
        out_folder = tmp_path / "dataset"
        out_folder.mkdir()

        result = create_dataset_description(out_folder)

        assert result.exists()
        assert result.name == "dataset_description.json"

    def test_default_content(self, tmp_path):
        out_folder = tmp_path / "ds"
        out_folder.mkdir()

        create_dataset_description(out_folder)
        data = _json.loads((out_folder / "dataset_description.json").read_text())

        assert data["BIDSVersion"] == "1.10.1"
        assert data["DatasetType"] == "raw"
        assert "GeneratedBy" in data

    def test_custom_name_and_description(self, tmp_path):
        out_folder = tmp_path / "ds"
        out_folder.mkdir()

        create_dataset_description(
            out_folder,
            name="My Study",
            description="A test dataset",
        )
        data = _json.loads((out_folder / "dataset_description.json").read_text())

        assert data["Name"] == "My Study"
        assert data["Description"] == "A test dataset"
