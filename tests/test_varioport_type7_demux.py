import sys
from pathlib import Path

import numpy as np


project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import _decode_type7_multiplexed_periodic
from helpers.physio.convert_varioport import _extract_trigger_annotations_from_signal
from helpers.physio.convert_varioport import _build_channel_descriptions
from helpers.physio.convert_varioport import _build_channels_schema_block


def test_decode_type7_periodic_mixed_rates_schedule():
    channels = [
        {
            "name": "ekg",
            "dsize": 1,
            "fs": 4.0,
            "doffs": 0,
            "mul": 1,
            "div": 1,
        },
        {
            "name": "resp",
            "dsize": 1,
            "fs": 2.0,
            "doffs": 0,
            "mul": 1,
            "div": 1,
        },
    ]

    # base fs=4Hz, schedule over ticks:
    # t0: ekg,resp -> 10,100
    # t1: ekg      -> 11
    # t2: ekg,resp -> 12,101
    # t3: ekg      -> 13
    raw = bytes([10, 100, 11, 12, 101, 13])

    decoded, info = _decode_type7_multiplexed_periodic(raw, channels, 4.0)

    assert info["status"] == "decoded"
    assert info["consumed_bytes"] == len(raw)
    assert np.allclose(decoded["ekg"], np.array([10.0, 11.0, 12.0, 13.0]))
    assert np.allclose(decoded["resp"], np.array([100.0, 101.0]))


def test_decode_type7_periodic_single_slow_channel_does_not_stop_on_idle_ticks():
    channels = [
        {
            "name": "ekg",
            "dsize": 1,
            "fs": 2.0,
            "doffs": 0,
            "mul": 1,
            "div": 1,
        }
    ]

    # base fs=4Hz, period=2 -> channel due every second tick.
    # Decoder must not break on odd ticks with no due channels.
    raw = bytes([21, 22, 23, 24])

    decoded, info = _decode_type7_multiplexed_periodic(raw, channels, 4.0)

    assert info["status"] == "decoded"
    assert info["consumed_bytes"] == len(raw)
    assert np.allclose(decoded["ekg"], np.array([21.0, 22.0, 23.0, 24.0]))


def test_extract_trigger_annotations_from_signal_detects_edges_and_duration():
    # 10 Hz marker with two pulses: [1-3) and [5-8)
    marker = np.array([0, 1, 1, 0, 0, 2, 2, 2, 0], dtype=float)

    annotations = _extract_trigger_annotations_from_signal(marker, 10.0, "Marker")

    assert len(annotations) == 2
    assert annotations[0] == (0.1, 0.2, "Marker:1")
    assert annotations[1] == (0.5, 0.3, "Marker:2")


def test_extract_trigger_annotations_from_signal_handles_open_ended_pulse():
    marker = np.array([0, 0, 3, 3, 3], dtype=float)

    annotations = _extract_trigger_annotations_from_signal(marker, 5.0, "trigger")

    assert len(annotations) == 1
    assert annotations[0] == (0.4, 0.6, "trigger:3")


def test_build_channel_descriptions_marks_roles_and_trigger_note():
    channels = [
        {"name": "ekg", "unit": "uV", "fs": 256.0, "dsize": 2},
        {"name": "Marker", "unit": "bit", "fs": 1.0, "dsize": 1},
        {"name": "resp", "unit": "a.u.", "fs": 32.0, "dsize": 2},
    ]

    desc = _build_channel_descriptions(channels, effective_fs=256.0)

    assert desc["ekg"]["Role"] == "cardiac"
    assert desc["ekg"]["SamplingFrequencyStored"] == 256.0
    assert desc["Marker"]["Role"] == "trigger"
    assert "EDF+ annotations" in desc["Marker"]["Description"]
    assert desc["resp"]["Role"] == "respiration"


def test_build_channels_schema_block_uses_schema_keys_and_types():
    channels = [
        {"name": "ekg", "unit": "uV", "fs": 256.0, "dsize": 2},
        {"name": "Marker", "unit": "bit", "fs": 1.0, "dsize": 1},
    ]

    meta = _build_channels_schema_block(channels, effective_fs=256.0)

    assert meta["ekg"]["Units"] == "uV"
    assert meta["ekg"]["Type"] == "ECG"
    assert meta["ekg"]["SamplingFrequencyNative"] == 256.0
    assert meta["ekg"]["SamplingFrequencyStored"] == 256.0
    assert meta["Marker"]["Type"] == "TRIGGER"
    assert "EDF+ annotations" in meta["Marker"]["Description"]
