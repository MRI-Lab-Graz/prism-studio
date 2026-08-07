"""Tests for `prism_tools.py environment scan-mri`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that the Studio
GUI's Converter -> Environment/MRI tab "Scan Project MRI Data" action
(src.web.blueprints.conversion_environment_mri_scan_helpers.
build_mri_acquisition_table) had no CLI equivalent, despite being a pure,
Flask-independent function. The resulting TSV is designed to feed
straight into the already-CLI-reachable `environment convert --input`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.environment import cmd_environment_scan_mri  # noqa: E402


def _write_sidecar(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(project=None, output=None, json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestScanMri:
    def test_writes_tsv_with_acquisition_data(self, tmp_path, capsys):
        project = tmp_path / "project"
        _write_sidecar(
            project / "rawdata" / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.json",
            {"AcquisitionDateTime": "2026-02-26T14:30:00"},
        )
        output = tmp_path / "scan.tsv"

        cmd_environment_scan_mri(_args(project=str(project), output=str(output)))

        assert output.exists()
        df = pd.read_csv(output, sep="\t")
        assert "participant_id" in df.columns
        assert len(df) == 1
        out = capsys.readouterr().out
        assert "Wrote 1 row" in out
        assert "environment convert" in out  # points user at the next step

    def test_json_mode_reports_stats(self, tmp_path, capsys):
        project = tmp_path / "project"
        _write_sidecar(
            project / "rawdata" / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.json",
            {"AcquisitionDateTime": "2026-02-26T14:30:00"},
        )
        output = tmp_path / "scan.tsv"

        cmd_environment_scan_mri(
            _args(project=str(project), output=str(output), json=True)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["row_count"] == 1
        assert payload["stats"]["subjects_found"] == 1

    def test_missing_project_directory_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_environment_scan_mri(
                _args(
                    project=str(tmp_path / "missing"), output=str(tmp_path / "out.tsv")
                )
            )
        assert exc_info.value.code == 1
        assert "not a directory" in capsys.readouterr().out

    def test_no_acquisition_timestamps_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        _write_sidecar(
            project / "rawdata" / "sub-01" / "anat" / "sub-01_T1w.json",
            {"Manufacturer": "Siemens"},
        )
        output = tmp_path / "scan.tsv"

        with pytest.raises(SystemExit) as exc_info:
            cmd_environment_scan_mri(_args(project=str(project), output=str(output)))
        assert exc_info.value.code == 1
        assert "No MRI acquisition timestamps" in capsys.readouterr().out
        assert not output.exists()

    def test_no_acquisition_timestamps_json_mode(self, tmp_path, capsys):
        project = tmp_path / "project"
        _write_sidecar(
            project / "rawdata" / "sub-01" / "anat" / "sub-01_T1w.json",
            {"Manufacturer": "Siemens"},
        )
        output = tmp_path / "scan.tsv"

        with pytest.raises(SystemExit):
            cmd_environment_scan_mri(
                _args(project=str(project), output=str(output), json=True)
            )
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False

    def test_reports_missing_timestamp_subjects(self, tmp_path, capsys):
        project = tmp_path / "project"
        _write_sidecar(
            project / "rawdata" / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.json",
            {"AcquisitionDateTime": "2026-02-26T14:30:00"},
        )
        _write_sidecar(
            project / "rawdata" / "sub-02" / "ses-01" / "anat" / "sub-02_ses-01_T1w.json",
            {"Manufacturer": "Siemens"},
        )
        output = tmp_path / "scan.tsv"

        cmd_environment_scan_mri(_args(project=str(project), output=str(output)))

        out = capsys.readouterr().out
        assert "Missing timestamp" in out
        assert "sub-02" in out
