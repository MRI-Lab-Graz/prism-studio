from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

from src.cli.commands.dataset import cmd_dataset_build_biometrics_smoketest


def _write_minimal_codebook(path: Path) -> None:
    """A codebook with one item ('resting_hr') in group 'fitness' — enough
    for process_excel_biometrics' header-detection (header=None read) and
    the command's own item_id/group column-presence checks (header=0
    read) to both succeed against the same real .xlsx file."""
    pd.DataFrame(
        [{"item_id": "resting_hr", "group": "fitness", "description": "Resting HR"}]
    ).to_excel(path, index=False, engine="openpyxl")


def _namespace(codebook: Path, data: Path, output: Path, library_root: Path) -> Namespace:
    return Namespace(
        codebook=str(codebook),
        sheet=0,
        data=str(data),
        output=str(output),
        library_root=str(library_root),
        name="smoketest",
        authors=None,
        session="ses-01",
        equipment="Legacy/Imported",
        supervisor="investigator",
    )


def test_build_biometrics_smoketest_rejects_case_only_colliding_participant_ids(
    tmp_path: Path, capsys
) -> None:
    """Regression guard: two participant ids differing only by case
    (e.g. 'sub-Ab'/'sub-ab') resolve to the identical on-disk directory
    on a case-insensitive filesystem (default macOS/Windows) — the
    second one written would silently overwrite the first's biometrics
    files with no error. Fail fast instead, before any output is
    written."""
    codebook = tmp_path / "codebook.xlsx"
    _write_minimal_codebook(codebook)

    data_csv = tmp_path / "dummy_data.csv"
    pd.DataFrame(
        [
            {"participant_id": "sub-Ab", "resting_hr": 60},
            {"participant_id": "sub-ab", "resting_hr": 99},
        ]
    ).to_csv(data_csv, index=False)

    output = tmp_path / "out"
    library_root = tmp_path / "library"

    args = _namespace(codebook, data_csv, output, library_root)

    try:
        cmd_dataset_build_biometrics_smoketest(args)
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code == 1

    assert raised, "expected the command to exit(1) rather than write colliding output"
    captured = capsys.readouterr()
    assert "differ only by case" in captured.out
    assert not output.exists()


def test_build_biometrics_smoketest_succeeds_with_distinct_ids(tmp_path: Path) -> None:
    codebook = tmp_path / "codebook.xlsx"
    _write_minimal_codebook(codebook)

    data_csv = tmp_path / "dummy_data.csv"
    pd.DataFrame(
        [
            {"participant_id": "sub-001", "resting_hr": 60},
            {"participant_id": "sub-002", "resting_hr": 70},
        ]
    ).to_csv(data_csv, index=False)

    output = tmp_path / "out"
    library_root = tmp_path / "library"

    args = _namespace(codebook, data_csv, output, library_root)
    cmd_dataset_build_biometrics_smoketest(args)

    assert (output / "sub-001" / "ses-01" / "biometrics").exists()
    assert (output / "sub-002" / "ses-01" / "biometrics").exists()
