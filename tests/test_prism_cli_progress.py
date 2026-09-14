"""Tests for the CLI validate progress indicator extracted from app/prism.py's
main().

`validate_dataset` (app/src/runner.py) already accepts a `progress_callback`
and the Studio GUI wires one up (app/src/web/blueprints/validation.py), but
the CLI (`prism.py <dataset>`) never passed one, so a long validation runs
silently with no sign it's still working. `make_cli_progress_reporter`
builds that callback: a single overwriting status line on stderr for normal
runs, and no callback at all for machine-readable output (--json/--format),
which must stay uncluttered.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

os.environ.setdefault("PRISM_SKIP_VENV_CHECK", "1")


def _load_prism_module():
    spec = importlib.util.spec_from_file_location(
        "prism_cli_under_test", APP_ROOT / "prism.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prism = _load_prism_module()


class TestMakeCliProgressReporter:
    def test_returns_none_in_machine_output_mode(self):
        assert prism.make_cli_progress_reporter(machine_output=True) is None

    def test_returns_callable_when_not_machine_output(self):
        reporter = prism.make_cli_progress_reporter(machine_output=False)
        assert callable(reporter)

    def test_writes_percent_and_message_to_stderr_only(self, capsys):
        reporter = prism.make_cli_progress_reporter(machine_output=False)
        reporter(50, 100, "Checking subjects...", None)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "50%" in captured.err
        assert "Checking subjects..." in captured.err

    def test_final_call_ends_with_newline_so_output_stays_readable(self, capsys):
        reporter = prism.make_cli_progress_reporter(machine_output=False)
        reporter(100, 100, "Done", None)
        assert capsys.readouterr().err.endswith("\n")

    def test_zero_total_does_not_raise(self, capsys):
        reporter = prism.make_cli_progress_reporter(machine_output=False)
        reporter(0, 0, "Starting...", None)
        assert "0%" in capsys.readouterr().err
