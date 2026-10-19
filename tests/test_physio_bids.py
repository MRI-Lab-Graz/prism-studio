import gzip
import json
import sys

import numpy as np
import pytest

from src.batch_convert import physio_target_folder
from src.physio_bids import edf_to_bids_physio, read_edf, write_bids_physio


def test_target_folder_no_task_is_physio():
    assert physio_target_folder(None, None) == "physio"
    assert physio_target_folder("", "beh") == "physio"


@pytest.mark.parametrize("dest", [None, "anat"])
def test_target_folder_task_needs_destination(dest):
    with pytest.raises(ValueError, match="beh, func, eeg"):
        physio_target_folder("rest", dest)


def test_target_folder_task_with_destination():
    assert physio_target_folder("rest", "func") == "func"


def test_write_bids_physio_files(tmp_path):
    ch = {"ecg": np.arange(5.0), "resp": np.arange(5.0) * 2}
    out = write_bids_physio(ch, sampling_frequency=256, start_time=0.0, out_base=tmp_path / "s_physio")
    assert [p.name for p in out] == ["s_physio.tsv.gz", "s_physio.json"]
    with gzip.open(out[0], "rt") as fh:
        arr = np.loadtxt(fh)
    assert arr.shape == (5, 2) and arr[2, 1] == 4.0
    meta = json.loads(out[1].read_text())
    assert meta["Columns"] == ["ecg", "resp"]
    assert meta["SamplingFrequency"] == 256.0 and meta["StartTime"] == 0.0


def test_read_edf_roundtrip(tmp_path, make_edf):
    ecg = np.linspace(-50, 50, 8)
    resp = np.linspace(0, 20, 4)
    p = make_edf(tmp_path / "a.edf", {"ecg": (ecg, 4), "resp": (resp, 2)}, duration=2.0)
    ch, rates, start = read_edf(p)
    assert list(ch) == ["ecg", "resp"]
    assert rates == {"ecg": 4.0, "resp": 2.0}
    np.testing.assert_allclose(ch["ecg"], ecg, atol=0.01)
    np.testing.assert_allclose(ch["resp"], resp, atol=0.01)
    assert start == 0.0


def test_read_edf_rejects_truncated(tmp_path, make_edf):
    p = make_edf(tmp_path / "a.edf", {"ecg": (np.zeros(8), 4)})
    p.write_bytes(p.read_bytes()[:-6])
    with pytest.raises(ValueError, match="not a valid EDF file"):
        read_edf(p)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        edf_to_bids_physio(p, out, "sub-01_task-x", "ecg")
    assert list(out.iterdir()) == []


def test_edf_to_bids_works_without_pyedflib(tmp_path, make_edf, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyedflib", None)
    p = make_edf(tmp_path / "a.edf", {"ecg": (np.arange(8.0), 4)})
    out = edf_to_bids_physio(p, tmp_path, "sub-01", "ecg")
    assert [x.name for x in out] == ["sub-01_recording-ecg_physio.tsv.gz", "sub-01_recording-ecg_physio.json"]


def test_edf_to_bids_groups_by_rate(tmp_path, make_edf):
    p = make_edf(tmp_path / "a.edf", {"ecg": (np.zeros(512), 256), "resp": (np.zeros(64), 32)}, duration=2.0)
    out = edf_to_bids_physio(p, tmp_path, "sub-01", "phys")
    names = sorted(x.name for x in out if x.suffix == ".json")
    assert names == ["sub-01_recording-phys256hz_physio.json", "sub-01_recording-phys32hz_physio.json"]
    assert json.loads((tmp_path / names[0]).read_text())["Columns"] == ["ecg"]


def test_read_edf_rejects_duplicate_labels(tmp_path, make_edf):
    p = make_edf(tmp_path / "d.edf", {"aa": (np.zeros(4), 4), "bb": (np.zeros(4), 4)})
    raw = bytearray(p.read_bytes())
    raw[256 + 16 : 256 + 32] = b"aa".ljust(16)  # second label becomes "aa"
    p.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="duplicate channel label"):
        read_edf(p)


def test_read_edf_rejects_file_without_signal_channels(tmp_path, make_edf):
    p = make_edf(tmp_path / "a.edf", {"EDF Annotations": (np.zeros(4), 4)})
    with pytest.raises(ValueError, match="no signal channels"):
        read_edf(p)


def test_tsv_gz_is_byte_stable(tmp_path):
    ch = {"ecg": np.arange(5.0)}
    a = write_bids_physio(ch, sampling_frequency=1, start_time=0, out_base=tmp_path / "a")[0]
    b = write_bids_physio(ch, sampling_frequency=1, start_time=0, out_base=tmp_path / "b")[0]
    assert a.read_bytes() == b.read_bytes()


def test_edf_to_bids_creates_out_dir_only_after_validation(tmp_path, make_edf):
    bad = tmp_path / "bad.edf"
    bad.write_bytes(b"x" * 300)
    with pytest.raises(ValueError):
        edf_to_bids_physio(bad, tmp_path / "out" / "beh", "sub-01", "ecg")
    assert not (tmp_path / "out").exists()
    good = make_edf(tmp_path / "ok.edf", {"ecg": (np.zeros(4), 4)})
    edf_to_bids_physio(good, tmp_path / "out" / "beh", "sub-01", "ecg")
    assert (tmp_path / "out" / "beh" / "sub-01_recording-ecg_physio.tsv.gz").exists()
