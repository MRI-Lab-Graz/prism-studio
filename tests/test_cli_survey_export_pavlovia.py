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
from tests.template_fixtures import complete, dump_complete

DEMO_PATH = (
    Path(__file__).resolve().parent.parent
    / "official"
    / "library"
    / "survey"
    / "survey-demo.json"
)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(json_path="", output=None, experiment_name=None, language=None)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.skipif(not DEMO_PATH.exists(), reason="Global library not available")
class TestExportPavlovia:
    def test_exports_psyexp_file_from_template(self, tmp_path, capsys):
        output_dir = tmp_path / "out"
        cmd_survey_export_pavlovia(
            _args(
                json_path=str(DEMO_PATH),
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

    def test_language_flag_passed_through(self, tmp_path, capsys):
        import json

        json_path = tmp_path / "task-demo_survey.json"
        json_path.write_text(
            dump_complete({
                    "I18n": {"Languages": ["en", "de"], "DefaultLanguage": "en"},
                    "Study": {"TaskName": "demo"},
                    "q1": {"Description": {"en": "Mood today", "de": "Stimmung heute"}},
                }
            ),
            encoding="utf-8",
        )
        output_dir = tmp_path / "out"
        cmd_survey_export_pavlovia(
            _args(json_path=str(json_path), output=str(output_dir), language="de")
        )

        psyexp_text = (output_dir / "demo.psyexp").read_text(encoding="utf-8")
        assert "Stimmung heute" in psyexp_text
        assert "Mood today" not in psyexp_text


@pytest.mark.skipif(not DEMO_PATH.exists(), reason="Global library not available")
def test_include_keeps_only_the_listed_questions(tmp_path):
    output_dir = tmp_path / "out"
    cmd_survey_export_pavlovia(
        _args(json_path=str(DEMO_PATH), output=str(output_dir), include="DEMO01,DEMO02")
    )

    text = " ".join(p.read_text() for p in output_dir.iterdir() if p.suffix in (".psyexp", ".csv"))
    assert "DEMO01" in text and "DEMO02" in text
    assert "DEMO03" not in text
