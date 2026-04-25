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
        task="rest",
        suffix="physio",
        sampling_rate=None,
    )

    cmd_convert_physio(args)

    assert output_dir.joinpath(
        "sub-01",
        "ses-01",
        "physio",
        "sub-01_ses-01_task-rest_recording-ecg_physio.edf",
    ).exists()
    assert output_dir.joinpath("task-rest_recording-ecg_physio.json").exists()
