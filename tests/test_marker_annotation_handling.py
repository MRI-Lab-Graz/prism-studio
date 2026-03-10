"""Test proper marker/annotation handling for Varioport EDF+ conversion.

Tests that marker information is properly extracted and documented in PRISM sidecars.
Based on EDF+ spec section 2.2 (Time-stamped Annotations Lists).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import (
    _extract_trigger_annotations_from_signal,
    _build_channel_descriptions,
    _infer_recording_type,
)

sys.path.insert(0, str(project_root))
from src.batch_convert import _create_physio_sidecar


class TestTriggerAnnotationExtraction:
    """Test extraction of trigger/marker events from signal data."""

    def test_extract_trigger_annotations_from_signal_detects_edges_and_duration(self):
        """Test marker edge detection with proper timing."""
        # 10 Hz marker with two pulses: [1-3) and [5-8)
        marker = np.array([0, 1, 1, 0, 0, 2, 2, 2, 0], dtype=float)

        annotations = _extract_trigger_annotations_from_signal(marker, 10.0, "Marker")

        assert len(annotations) == 2
        assert annotations[0] == (0.1, 0.0, "Marker:1")
        assert annotations[1] == (0.5, 0.0, "Marker:2")

    def test_extract_trigger_annotations_from_signal_handles_open_ended_pulse(self):
        """Test handling of pulses that run to end of signal."""
        marker = np.array([0, 0, 3, 3, 3], dtype=float)

        annotations = _extract_trigger_annotations_from_signal(marker, 5.0, "trigger")

        assert len(annotations) == 1
        assert annotations[0] == (0.4, 0.0, "trigger:3")

    def test_extract_trigger_annotations_empty_signal(self):
        """Test handling of empty marker signal."""
        marker = np.array([], dtype=float)

        annotations = _extract_trigger_annotations_from_signal(marker, 10.0, "Marker")

        assert len(annotations) == 0

    def test_extract_trigger_annotations_all_zeros(self):
        """Test signal with no marker events."""
        marker = np.array([0, 0, 0, 0], dtype=float)

        annotations = _extract_trigger_annotations_from_signal(marker, 10.0, "Marker")

        assert len(annotations) == 0


class TestChannelDescriptions:
    """Test building channel descriptions for EDF+ and PRISM sidecars."""

    def test_build_channel_descriptions_marks_roles_and_types(self):
        """Test channel type and role inference."""
        channels = [
            {"name": "ekg", "unit": "uV", "fs": 256.0, "dsize": 2},
            {"name": "Marker", "unit": "bit", "fs": 1.0, "dsize": 1},
            {"name": "resp", "unit": "a.u.", "fs": 32.0, "dsize": 2},
        ]

        desc = _build_channel_descriptions(channels, effective_fs=256.0)

        assert desc["ekg"]["Type"] == "ECG"
        assert desc["ekg"]["Role"] == "cardiac"
        assert desc["Marker"]["Type"] == "TRIGGER"
        assert desc["Marker"]["Role"] == "trigger"
        assert desc["resp"]["Type"] == "RESP"
        assert desc["resp"]["Role"] == "respiration"

    def test_build_channel_descriptions_includes_sampling_rates(self):
        """Test that native and stored sampling rates are documented."""
        channels = [{"name": "ekg", "unit": "uV", "fs": 256.0}]

        desc = _build_channel_descriptions(channels, effective_fs=256.0)

        assert desc["ekg"]["SamplingFrequencyNative"] == 256.0
        assert desc["ekg"]["SamplingFrequencyStored"] == 256.0

    def test_build_channel_descriptions_trigger_annotation_mention(self):
        """Test that trigger channels reference EDF+ TAL spec."""
        channels = [{"name": "Marker", "unit": "bit", "fs": 1.0}]

        desc = _build_channel_descriptions(channels, effective_fs=256.0)

        assert "EDF+" in desc["Marker"]["Description"]
        assert "TAL" in desc["Marker"]["Description"]
        assert "2.2.2" in desc["Marker"]["Description"]


class TestRecordingTypeInference:
    """Test recording type inference from channel composition."""

    def test_infer_recording_type_ecg_only(self):
        """Test inference for ECG-only recording."""
        channels = [{"name": "ekg"}]

        rtype = _infer_recording_type(channels)

        assert rtype == "ecg"

    def test_infer_recording_type_ecg_resp(self):
        """Test inference for ECG + respiration."""
        channels = [
            {"name": "ekg"},
            {"name": "resp"},
        ]

        rtype = _infer_recording_type(channels)

        assert rtype in ("mixed", "ecg")

    def test_infer_recording_type_mixed_signals(self):
        """Test inference for multi-modality recording."""
        channels = [
            {"name": "ekg"},
            {"name": "resp"},
            {"name": "eda"},
        ]

        rtype = _infer_recording_type(channels)

        assert rtype == "mixed"


class TestPhysioSidecarWithAnnotations:
    """Test that physio sidecars properly document marker information."""

    def test_create_physio_sidecar_includes_annotation_block(self, tmp_path):
        """Test that Annotations section is created in sidecar."""
        source = tmp_path / "sub-01_task-rest.edf"
        source.write_bytes(b"EDF")

        output_json = tmp_path / "sub-01_task-rest_physio.json"

        _create_physio_sidecar(
            source,
            output_json,
            task_name="task-rest",
            sampling_rate=256.0,
            extra_meta={"Channels": ["ekg", "Marker"]},
        )

        sidecar = json.loads(output_json.read_text(encoding="utf-8"))

        assert "Annotations" in sidecar
        assert "MarkerEvents" in sidecar["Annotations"]
        assert "Format" in sidecar["Annotations"]
        assert "EDF+" in sidecar["Annotations"]["Description"]

    def test_create_physio_sidecar_documents_channel_roles(self, tmp_path):
        """Test that channel roles are properly documented."""
        source = tmp_path / "sub-01_task-rest.edf"
        source.write_bytes(b"EDF")

        output_json = tmp_path / "sub-01_task-rest_physio.json"

        _create_physio_sidecar(
            source,
            output_json,
            task_name="task-rest",
            sampling_rate=256.0,
            extra_meta={"Channels": ["ekg", "Marker"]},
        )

        sidecar = json.loads(output_json.read_text(encoding="utf-8"))

        assert "Channels" in sidecar
        assert "ekg" in sidecar["Channels"]
        assert sidecar["Channels"]["ekg"]["Role"] == "cardiac"
        assert sidecar["Channels"]["ekg"]["Type"] == "ECG"
        assert "Marker" in sidecar["Channels"]
        assert sidecar["Channels"]["Marker"]["Role"] == "trigger"
        assert sidecar["Channels"]["Marker"]["Type"] == "TRIGGER"

    def test_create_physio_sidecar_marks_marker_events_section(self, tmp_path):
        """Test that marker events are documented with TAL reference."""
        source = tmp_path / "sub-01_task-rest_recording-ecg_physio.edf"
        source.write_bytes(b"EDF")

        output_json = tmp_path / "sub-01_task-rest_recording-ecg_physio.json"

        marker_events = [
            {"onset": 10.5, "duration": 0.0, "annotation": "event:1"},
            {"onset": 25.3, "duration": 0.0, "annotation": "event:2"},
        ]

        _create_physio_sidecar(
            source,
            output_json,
            task_name="task-rest",
            sampling_rate=256.0,
            extra_meta={"Channels": ["ekg", "Marker"], "MarkerEvents": marker_events},
        )

        sidecar = json.loads(output_json.read_text(encoding="utf-8"))

        assert sidecar["Annotations"]["MarkerEvents"] == marker_events

    def test_create_physio_sidecar_includes_prism_schema_version(self, tmp_path):
        """Test that PRISM schema version is documented."""
        source = tmp_path / "sub-01_task-rest.edf"
        source.write_bytes(b"EDF")

        output_json = tmp_path / "sub-01_task-rest_physio.json"

        _create_physio_sidecar(
            source,
            output_json,
            task_name="task-rest",
            sampling_rate=256.0,
        )

        sidecar = json.loads(output_json.read_text(encoding="utf-8"))

        assert "SchemaVersion" in sidecar["Metadata"]
        assert sidecar["Metadata"]["SchemaVersion"] == "1.2.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
