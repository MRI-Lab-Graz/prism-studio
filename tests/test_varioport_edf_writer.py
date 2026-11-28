"""Varioport EDF output (edfio): what a reader gets back from the headers and samples the converter builds."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

edfio = pytest.importorskip("edfio")


def _header(label, unit, low, high, fs=256):
    return {"label": label, "dimension": unit, "sample_frequency": fs, "physical_min": low, "physical_max": high,
            "digital_min": -32768, "digital_max": 32767, "transducer": "Varioport", "prefilter": ""}


def test_edf_writer_pads_clips_and_shortens_like_the_recording_needs(tmp_path):
    from helpers.physio.convert_varioport import _EdfWriter

    writer = _EdfWriter(tmp_path / "out.edf")
    writer.setSignalHeaders([_header("EKG", "µV", -50000, 50000), _header("a_very_long_channel_name", "mV", -100, 100)])
    writer.writeAnnotation(1.0, 0.5, "Marker:3")
    writer.writeSamples([np.linspace(-60000, 60000, 640), np.full(640, 12.5)])  # 2.5 s
    writer.close()

    edf = edfio.read_edf(tmp_path / "out.edf")
    ecg, long = edf.signals
    assert edf.labels == ("EKG", "a_very_long_chan")
    assert (ecg.physical_dimension, ecg.sampling_frequency, ecg.transducer_type) == ("uV", 256, "Varioport")
    assert len(ecg.data) == 768 and edf.duration == 3  # the last record is filled with zeros
    assert ecg.data.min() == pytest.approx(-50000, abs=1) and ecg.data[:640].max() == pytest.approx(50000, abs=1)
    assert long.data[0] == pytest.approx(12.5, abs=0.01) and long.data[-1] == pytest.approx(0, abs=0.01)
    assert [(a.onset, a.duration, a.text) for a in edf.annotations] == [(1.0, 0.5, "Marker:3")]


def test_edf_writer_keeps_a_fractional_sampling_rate(tmp_path):
    from helpers.physio.convert_varioport import _EdfWriter

    writer = _EdfWriter(tmp_path / "out.edf")
    writer.setSignalHeaders([_header("EKG", "uV", -1, 1, fs=512 / 3)])
    writer.writeSamples([np.zeros(500)])
    writer.close()

    assert edfio.read_edf(tmp_path / "out.edf").signals[0].sampling_frequency == pytest.approx(512 / 3, abs=1e-4)


def test_edf_writer_takes_nul_padded_header_names(tmp_path):
    """The RAW header pads names with NULs; they end the name, as they did for pyedflib."""
    from helpers.physio.convert_varioport import _EdfWriter

    writer = _EdfWriter(tmp_path / "out.edf")
    writer.setSignalHeaders([_header("EKG\x00\x00\x00", "uV\x00\x00", -1, 1), _header("a\x01b", "V", -1, 1)])
    writer.writeSamples([np.zeros(256), np.zeros(256)])
    writer.close()

    edf = edfio.read_edf(tmp_path / "out.edf")
    assert edf.labels == ("EKG", "a?b") and edf.signals[0].physical_dimension == "uV"


@pytest.mark.parametrize("headers, samples", [([], []), ([_header("EKG", "uV", -1, 1)], [np.zeros(0)])])
def test_edf_writer_says_when_there_is_nothing_to_write(tmp_path, headers, samples):
    from helpers.physio.convert_varioport import _EdfWriter

    writer = _EdfWriter(tmp_path / "out.edf")
    writer.setSignalHeaders(headers)
    writer.writeSamples(samples)
    with pytest.raises(ValueError, match="no samples were written"):
        writer.close()
