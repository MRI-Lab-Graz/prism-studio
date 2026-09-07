"""Tests for `prism_tools.py survey export-pavlovia`.

Mirrors tests/test_cli_survey_export_commands.py (export-lss): calls the CLI
command handler directly with a SimpleNamespace standing in for parsed argparse
args, rather than shelling out to a subprocess.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.survey import cmd_survey_export_pavlovia  # noqa: E402

GAD7_PATH = (
    Path(__file__).resolve().parent.parent
    / "official"
    / "library"
    / "survey"
    / "survey-gad7.json"
)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(json_path="", output=None, experiment_name=None)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.skipif(not GAD7_PATH.exists(), reason="Global library not available")
class TestExportPavlovia:
    def test_exports_psyexp_file_from_template(self, tmp_path, capsys):
        output_dir = tmp_path / "out"
        cmd_survey_export_pavlovia(
            _args(
                json_path=str(GAD7_PATH),
                output=str(output_dir),
                experiment_name="demo",
            )
        )

        assert (output_dir / "demo.psyexp").exists()
        assert "written" in capsys.readouterr().out

    def test_missing_file_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_export_pavlovia(
                _args(json_path=str(tmp_path / "missing.json"))
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out
