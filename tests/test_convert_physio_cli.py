import sys
from argparse import Namespace
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from src.cli.commands.convert import cmd_convert_physio


def test_cmd_convert_physio_accepts_single_file(tmp_path, monkeypatch) -> None:
    raw_file = tmp_path / "signal.raw"
    raw_file.write_bytes(b"RAW")
    output_dir = tmp_path / "out"

    calls: list[tuple[str, str, str, str, float | None, bool]] = []

    def fake_convert_varioport(
        input_path: str,
        output_edf: str,
        output_json: str,
        *,
        task_name: str,
        base_freq: float | None = None,
        allow_raw_multiplexed: bool = False,
    ) -> None:
        Path(output_edf).write_bytes(b"EDF")
        Path(output_json).write_text("{}", encoding="utf-8")
        calls.append(
            (
                input_path,
                output_edf,
                output_json,
                task_name,
                base_freq,
                allow_raw_multiplexed,
            )
        )

    monkeypatch.setattr(
        "src.cli.commands.convert.convert_varioport", fake_convert_varioport
    )

    args = Namespace(
        input=str(raw_file),
        output=str(output_dir),
        task="rest",
        suffix="physio",
        sampling_rate=256.0,
    )

    cmd_convert_physio(args)

    assert len(calls) == 1
    assert calls[0][0] == str(raw_file)
    assert calls[0][3] == "rest"
    assert calls[0][4] == 256.0
    assert output_dir.joinpath("signal.edf").exists()
    assert output_dir.joinpath("signal.json").exists()


def test_cmd_convert_physio_directory_mode_accepts_vpd_files(
    tmp_path, monkeypatch
) -> None:
    input_dir = tmp_path / "sourcedata"
    raw_dir = input_dir / "sub-01" / "ses-01"
    raw_dir.mkdir(parents=True)
    vpd_file = raw_dir / "sub-01_ses-01_task-rest.vpd"
    vpd_file.write_bytes(b"VPD")
    output_dir = tmp_path / "rawdata"

    def fake_convert_varioport(
        input_path: str,
        output_edf: str,
        output_json: str,
        *,
        task_name: str,
        base_freq: float | None = None,
        allow_raw_multiplexed: bool = False,
    ) -> None:
        Path(output_edf).parent.mkdir(parents=True, exist_ok=True)
        Path(output_edf).write_bytes(b"EDF")
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(output_json).write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "src.cli.commands.convert.convert_varioport", fake_convert_varioport
    )

    args = Namespace(
        input=str(input_dir),
        output=str(output_dir),
        task=None,
        suffix="physio",
        sampling_rate=None,
    )

    cmd_convert_physio(args)

    folder = output_dir / "sub-01" / "ses-01" / "physio"
    assert (folder / "sub-01_ses-01_recording-ecg_physio.edf").exists()
    assert (folder / "sub-01_ses-01_recording-ecg_physio.json").exists()


def _dir_input(tmp_path):
    raw_dir = tmp_path / "sourcedata" / "sub-01" / "ses-01"
    raw_dir.mkdir(parents=True)
    (raw_dir / "sub-01_ses-01.vpd").write_bytes(b"VPD")
    return tmp_path / "sourcedata", tmp_path / "rawdata"


def _fake_bids(input_path, output_edf, output_json, *, task_name, base_freq=None,
               allow_raw_multiplexed=False, bids_base=None):
    if bids_base is not None:
        Path(bids_base).parent.mkdir(parents=True, exist_ok=True)
        Path(str(bids_base) + ".tsv.gz").write_bytes(b"x" * 20000)
        Path(str(bids_base) + ".json").write_text("{}", encoding="utf-8")
        return
    Path(output_edf).write_bytes(b"E" * 20000)
    Path(output_json).write_text("{}", encoding="utf-8")


def _args(inp, out, **kw):
    base = dict(input=str(inp), output=str(out), task=None, destination=None,
                suffix="physio", sampling_rate=None)
    base.update(kw)
    return Namespace(**base)


def test_no_task_writes_physio_folder_without_task_entity(tmp_path, monkeypatch) -> None:
    inp, out = _dir_input(tmp_path)
    monkeypatch.setattr("src.cli.commands.convert.convert_varioport", _fake_bids)
    cmd_convert_physio(_args(inp, out))
    names = sorted(p.name for p in (out / "sub-01" / "ses-01" / "physio").iterdir())
    assert names == [
        "sub-01_ses-01_recording-ecg_physio.edf",
        "sub-01_ses-01_recording-ecg_physio.json",
    ]
    assert not any("task-" in str(p) for p in out.rglob("*"))


def test_task_without_destination_exits_2_and_writes_nothing(
    tmp_path, monkeypatch, capsys
) -> None:
    import pytest

    inp, out = _dir_input(tmp_path)
    monkeypatch.setattr("src.cli.commands.convert.convert_varioport", _fake_bids)
    with pytest.raises(SystemExit) as exc:
        cmd_convert_physio(_args(inp, out, task="rest"))
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "beh" in err and "func" in err and "eeg" in err
    assert not out.exists()


def test_task_with_destination_writes_bids_files(tmp_path, monkeypatch) -> None:
    import sys as _sys

    inp, out = _dir_input(tmp_path)
    monkeypatch.setitem(_sys.modules, "pyedflib", None)
    monkeypatch.setattr("src.cli.commands.convert.convert_varioport", _fake_bids)
    cmd_convert_physio(_args(inp, out, task="rest", destination="beh"))
    folder = out / "sub-01" / "ses-01" / "beh"
    base = "sub-01_ses-01_task-rest_recording-ecg_physio"
    assert (folder / f"{base}.tsv.gz").exists()
    assert (folder / f"{base}.json").exists()
    assert not (out / "sub-01" / "ses-01" / "physio").exists()


def test_destination_without_task_warns_that_it_is_ignored(tmp_path, monkeypatch, capsys) -> None:
    inp, out = _dir_input(tmp_path)
    monkeypatch.setattr("src.cli.commands.convert.convert_varioport", _fake_bids)
    cmd_convert_physio(_args(inp, out, destination="beh"))
    assert "--destination is ignored without --task: files go to physio/" in capsys.readouterr().err
    assert (out / "sub-01" / "ses-01" / "physio" / "sub-01_ses-01_recording-ecg_physio.edf").exists()


def test_single_file_with_task_and_no_destination_writes_flat_output(tmp_path, monkeypatch) -> None:
    """Single-file mode: task is only a label, no destination needed, output stays flat."""
    raw = tmp_path / "signal.raw"
    raw.write_bytes(b"RAW")
    out = tmp_path / "out"
    monkeypatch.setattr("src.cli.commands.convert.convert_varioport", _fake_bids)
    cmd_convert_physio(_args(raw, out, task="rest"))
    assert (out / "signal.edf").exists() and (out / "signal.json").exists()
