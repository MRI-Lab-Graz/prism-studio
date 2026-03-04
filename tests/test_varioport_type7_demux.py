import sys
from pathlib import Path

import numpy as np


project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import _decode_type7_multiplexed_periodic


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
