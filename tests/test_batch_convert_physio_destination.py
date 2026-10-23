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
    (src / "sub-01_ses-pre.tsv").write_text("a\tb\n")  # generic table
    out = tmp_path / "out"
    result = batch_convert_folder(src, out, modality_filter="all")
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


def test_failed_dry_run_leaves_no_staging_dir(tmp_path, make_edf, monkeypatch):
    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(tmp))
    with pytest.raises(ValueError):
        batch_convert_folder(src, tmp_path / "out", dry_run=True)
    assert list(tmp.iterdir()) == []


def _raw_src(tmp_path, name):
    src = tmp_path / "rawsrc"
    src.mkdir()
    (src / name).write_bytes(b"raw")
    return src


def _stub(calls, fail_first=False):
    def fake(raw, edf, js, **kw):
        calls.append(kw)
        if fail_first and len(calls) == 1:
            raise ValueError("Unsupported Varioport header type 7")
        if kw.get("bids_base") is not None:
            base = kw["bids_base"]
            base.with_name(base.name + ".tsv.gz").write_bytes(b"x")
            base.with_name(base.name + ".json").write_text("{}")
        else:
            open(edf, "wb").write(b"edf")
            open(js, "w").write("{}")
        return {}

    return fake


@pytest.mark.parametrize("fail_first", [False, True])
def test_task_bound_raw_uses_bids_base_in_destination(tmp_path, monkeypatch, fail_first):
    calls = []
    monkeypatch.setattr("helpers.physio.convert_varioport.convert_varioport", _stub(calls, fail_first))
    src = _raw_src(tmp_path, "sub-01_ses-1_task-stroop.raw")
    out = tmp_path / "out"
    result = batch_convert_folder(src, out, physio_destination="eeg")
    base = "sub-01_ses-1_task-stroop_recording-ecg_physio"
    assert [c["bids_base"] for c in calls] == [out / "sub-01/ses-1/eeg" / base] * len(calls)
    assert len(calls) == (2 if fail_first else 1)
    assert fail_first == bool(calls[-1].get("allow_raw_multiplexed"))
    assert result.success_count == 1
    assert sorted(f.name for f in result.converted[0].output_files) == [f"{base}.json", f"{base}.tsv.gz"]
    assert result.converted[0].target_folder == "eeg"


def test_task_free_raw_gets_no_bids_base_and_lands_in_physio(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("helpers.physio.convert_varioport.convert_varioport", _stub(calls))
    src = _raw_src(tmp_path, "sub-01_recording-ecg.raw")
    out = tmp_path / "out"
    result = batch_convert_folder(src, out)
    assert "bids_base" not in calls[0]
    assert (out / "sub-01/physio/sub-01_recording-ecg_physio.edf").exists()
    assert (out / "sub-01/physio/sub-01_recording-ecg_physio.json").exists()
    assert result.converted[0].target_folder == "physio"


def _converted(**kw):
    from pathlib import Path

    from src.batch_convert import ConvertedFile

    base = dict(
        source_path=Path("x.edf"), output_files=[], modality="physio",
        subject="sub-01", session="ses-pre", task=None, success=True,
    )
    base.update(kw)
    return ConvertedFile(**base)


def test_physio_report_for_task_free_file_does_not_say_none(tmp_path, make_edf):
    """Placeholder report (no pyedflib) for a task-free file: no 'None' in its name."""
    from src.batch_convert import _generate_physio_html_report

    edf = tmp_path / "sub-01_ses-pre_recording-ecg_physio.edf"
    make_edf(edf, {"ecg": (np.linspace(-1, 1, 8), 4)})
    report = _generate_physio_html_report(
        converted=_converted(output_files=[edf]), output_folder=tmp_path / "out"
    )
    assert report.name == "sub-01_ses-pre_physio_report.html"


def test_physio_report_main_path_handles_task_none(tmp_path, make_edf, monkeypatch):
    """The full report (needs pyedflib) must not crash on task=None; here a stub reader is enough to reach the task fields."""
    monkeypatch.delitem(sys.modules, "pyedflib", raising=False)  # drop the autouse block
    pytest.importorskip("pyedflib")
    from src.batch_convert import _generate_physio_html_report

    edf = tmp_path / "sub-01_ses-pre_recording-ecg_physio.edf"
    make_edf(edf, {"ecg": (np.sin(np.linspace(0, 60, 2000)), 200)}, duration=10.0)
    report = _generate_physio_html_report(
        converted=_converted(output_files=[edf]), output_folder=tmp_path / "out"
    )
    assert report is not None and "None" not in report.name


def test_task_bound_bids_output_logs_that_no_report_is_made(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    logs = []
    batch_convert_folder(
        src, tmp_path / "out", physio_destination="func",
        generate_physio_reports=True, log_callback=lambda m, lvl="info": logs.append(m),
    )
    assert any("no physio report" in m.lower() and "tsv.gz" in m for m in logs)


# --- cleanup wave -----------------------------------------------------------


def test_task_bound_raw_forwards_converter_stdout_to_log(tmp_path, monkeypatch):
    def fake(raw, edf, js, **kw):
        print("Average heart rate: 71 bpm")
        base = kw["bids_base"]
        base.with_name(base.name + ".tsv.gz").write_bytes(b"x")
        base.with_name(base.name + ".json").write_text("{}")
        return {}

    monkeypatch.setattr("helpers.physio.convert_varioport.convert_varioport", fake)
    src = _raw_src(tmp_path, "sub-01_task-stroop.raw")
    logs = []
    batch_convert_folder(
        src, tmp_path / "out", physio_destination="eeg",
        log_callback=lambda m, lvl="info": logs.append(m),
    )
    assert any("Average heart rate: 71 bpm" in m for m in logs)


def test_no_report_message_only_for_bids_output(tmp_path, make_edf, monkeypatch):
    """A task-free EDF whose report is None (e.g. no labels) must not claim it is BIDS .tsv.gz output."""
    monkeypatch.setattr("src.batch_convert._generate_physio_html_report", lambda **kw: None)
    src = _src(tmp_path, make_edf, "sub-01_recording-ecg.edf")
    logs = []
    batch_convert_folder(
        src, tmp_path / "out", generate_physio_reports=True,
        log_callback=lambda m, lvl="info": logs.append(m),
    )
    assert not any("no physio report" in m.lower() for m in logs)


def test_physio_renamer_import_is_in_top_import_block():
    import src.batch_convert as bc

    lines = open(bc.__file__, encoding="utf-8").read().splitlines()
    imp = next(i for i, l in enumerate(lines) if l.startswith("from src.physio_renamer import"))
    first_code = next(i for i, l in enumerate(lines) if l.startswith("PHYSIO_EXTENSIONS"))
    assert imp < first_code
    assert "noqa" not in lines[imp]


def _run_main(args, cwd):
    import subprocess

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    env = {**__import__("os").environ, "PYTHONPATH": str(root)}
    return subprocess.run(
        [sys.executable, "-m", "src.batch_convert", *map(str, args)],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def test_main_requires_destination_for_task_files(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    proc = _run_main([src, tmp_path / "out"], tmp_path)
    assert proc.returncode == 2
    assert "sub-01_task-stroop_recording-ecg.edf" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_main_destination_option_converts_task_files(tmp_path, make_edf):
    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    proc = _run_main([src, tmp_path / "out", "--destination", "func"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert any(f.startswith("sub-01/func/") for f in _rel(tmp_path / "out"))


def test_destination_problems_raise_the_dedicated_error(tmp_path, make_edf):
    from src.batch_convert import PhysioDestinationError, physio_target_folder

    assert issubclass(PhysioDestinationError, ValueError)
    with pytest.raises(PhysioDestinationError):
        physio_target_folder("task-x", None)
    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf")
    with pytest.raises(PhysioDestinationError):
        batch_convert_folder(src, tmp_path / "out")


def test_check_physio_destination_is_public_and_filters(tmp_path, make_edf):
    from src.batch_convert import PhysioDestinationError, check_physio_destination

    src = _src(tmp_path, make_edf, "sub-01_task-stroop_recording-ecg.edf", "sub-02_recording-ecg.edf")
    with pytest.raises(PhysioDestinationError, match="sub-01_task-stroop_recording-ecg.edf"):
        check_physio_destination(src, "all", None)
    check_physio_destination(src, "all", "beh")  # destination given: fine
    check_physio_destination(src, "survey", None)  # not physio: nothing to check
    assert not (tmp_path / "out").exists()
