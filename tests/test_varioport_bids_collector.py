"""_BidsCollector.finish() must fail with a clear message, not a numpy error."""

import sys
from pathlib import Path

import pytest

app_path = Path(__file__).resolve().parents[1] / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import _BidsCollector  # noqa: E402


def test_finish_without_samples_raises_clear_error(tmp_path):
    c = _BidsCollector(tmp_path / "x_physio")
    c.setSignalHeaders([{"label": "ecg", "sample_frequency": 100}])
    with pytest.raises(ValueError, match="no samples were written"):
        c.finish({})


def test_finish_with_unequal_lengths_raises_clear_error(tmp_path):
    c = _BidsCollector(tmp_path / "x_physio")
    c.setSignalHeaders(
        [
            {"label": "ecg", "sample_frequency": 100},
            {"label": "resp", "sample_frequency": 100},
        ]
    )
    c.writeSamples([[1.0, 2.0, 3.0], [1.0, 2.0]])
    with pytest.raises(ValueError, match="channels have different lengths"):
        c.finish({})
