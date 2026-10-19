"""Batch convert: task-free physio stays EDF in physio/, task-bound physio becomes BIDS tsv.gz."""

import gzip
import json
import sys
from argparse import Namespace

import numpy as np
import pytest

from src.batch_convert import batch_convert_folder, parse_bids_filename


@pytest.fixture(autouse=True)
def no_pyedflib(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyedflib", None)  # task-bound paths must never need it


def _rel(folder):
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def _src(tmp_path, make_edf, *names):
    src = tmp_path / "src"
    src.mkdir()
    for n in names:
        make_edf(src / n, {"ecg": (np.linspace(-1, 1, 8), 4)})
    return src


def test_parse_without_task():
    parsed = parse_bids_filename("sub-01_ses-pre_recording-ecg.edf")
    assert parsed["task"] is None and parsed["ses"] == "ses-pre"
    assert parsed["extra"] == "_recording-ecg"


def test_task_free_edf_lands_in_physio_unchanged(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_ses-pre_recording-ecg.edf")
    out = tmp_path / "out"
    result = batch_convert_folder(src, out)
    edf = out / "sub-01/ses-pre/physio/sub-01_ses-pre_recording-ecg_physio.edf"
    assert edf.read_bytes() == (src / "sub-01_ses-pre_recording-ecg.edf").read_bytes()
    assert edf.with_suffix(".json").exists()
    assert result.converted[0].target_folder == "physio" and result.success_count == 1


def test_task_bound_without_destination_raises_before_writing(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_recording-ecg.edf", "sub-01_task-stroop_recording-ecg.edf")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="sub-01_task-stroop_recording-ecg.edf"):
        batch_convert_folder(src, out)
    assert list(out.rglob("*")) == []


def test_task_bound_edf_goes_to_destination_as_tsv_gz(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_ses-pre_task-stroop_recording-ecg.edf")
    out = tmp_path / "out"
    result = batch_convert_folder(src, out, physio_destination="beh")
    stem = "sub-01/ses-pre/beh/sub-01_ses-pre_task-stroop_recording-ecg_physio"
    assert (out / f"{stem}.tsv.gz").exists() and (out / f"{stem}.json").exists()
    assert not list((out / "sub-01/ses-pre/beh").glob("*.edf"))
    assert result.converted[0].target_folder == "beh" and result.success_count == 1
    with gzip.open(out / f"{stem}.tsv.gz", "rt") as fh:
        assert np.loadtxt(fh).shape == (8,)


def test_dry_run_task_bound_writes_nothing(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    out = tmp_path / "out"
    out.mkdir()
    result = batch_convert_folder(src, out, physio_destination="func", dry_run=True)
    assert list(out.rglob("*")) == []
    assert result.new_files == 2
    assert {f.name for f in result.converted[0].output_files} == {
        "sub-01_task-stroop_recording-ecg_physio.tsv.gz",
        "sub-01_task-stroop_recording-ecg_physio.json",
    }
    assert all(out / "sub-01" / "func" in f.parents for f in result.converted[0].output_files)


def test_non_physio_file_without_task_is_skipped_with_message(tmp_path, make_edf):
    src = tmp_path / "src"
    src.mkdir()
    (src / "sub-01_ses-pre.tsv").write_text("a\tb\n")  # eyetracking trial table
    out = tmp_path / "out"
    result = batch_convert_folder(src, out, modality_filter="eyetracking")
    assert result.converted == []
    assert [(p.name, "task" in why) for p, why in result.skipped] == [("sub-01_ses-pre.tsv", True)]


def test_session_label_not_normalized(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_ses-1_recording-ecg.edf")
    out = tmp_path / "out"
    batch_convert_folder(src, out)
    assert any(f.startswith("sub-01/ses-1/physio/") for f in _rel(out))


def test_batch_convert_cli_requires_destination_for_task_files(tmp_path, make_edf, capsys):
    from src.cli.commands.convert import cmd_physio_batch_convert

    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    args = Namespace(input=str(src), output=str(tmp_path / "out"), modality="all", sampling_rate=None,
                     dry_run=False, destination=None)
    with pytest.raises(SystemExit) as exc:
        cmd_physio_batch_convert(args)
    assert exc.value.code == 2
    assert "sub-01_task-stroop_recording-ecg.edf" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_cli_destination_option_is_parsed():
    from pathlib import Path

    from src.cli.parser import build_prism_tools_parsers

    parser, _ = build_prism_tools_parsers(Path(__file__).resolve().parents[1] / "app")
    base = ["physio", "batch-convert", "--input", "a", "--output", "b"]
    assert parser.parse_args(base + ["--destination", "eeg"]).destination == "eeg"
    assert parser.parse_args(base).destination is None
    with pytest.raises(SystemExit):
        parser.parse_args(base + ["--destination", "anat"])


@pytest.mark.parametrize("module", ["helpers.physio.convert_varioport", "app.helpers.physio.convert_varioport"])
def test_bids_collector_writes_flat_sidecar(tmp_path, module):
    import importlib

    mod = importlib.import_module(module)
    c = mod._BidsCollector(tmp_path / "sub-01_task-x_recording-ecg_physio")
    c.setSignalHeaders([{"label": "EKG", "sample_frequency": 256.0}, {"label": "Marker", "sample_frequency": 256.0}])
    c.writeAnnotation(1.0, 0.0, "ignored")
    c.writeSamples([np.arange(4.0), np.zeros(4)])
    c.close()
    c.finish({"AverageHeartRateBPM": 61.5, "TaskName": "x"})
    meta = json.loads((tmp_path / "sub-01_task-x_recording-ecg_physio.json").read_text())
    assert meta == {"SamplingFrequency": 256.0, "StartTime": 0.0, "Columns": ["EKG", "Marker"],
                    "AverageHeartRateBPM": 61.5, "TaskName": "x"}
    with gzip.open(tmp_path / "sub-01_task-x_recording-ecg_physio.tsv.gz", "rt") as fh:
        assert np.loadtxt(fh).shape == (4, 2)
