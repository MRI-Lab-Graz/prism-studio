"""Importing Studio must not take over the process's exit code.

An ``atexit`` handler registered at import ended every pytest run with 0, so CI
was green while tests failed.
"""

import os
import subprocess
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1] / "app" / "prism-studio.py"

IMPORT_THEN = """
import importlib.util, sys
sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("studio_exit", {path!r})
spec.loader.exec_module(importlib.util.module_from_spec(spec))
{then}
"""


def _run(then: str) -> int:
    code = IMPORT_THEN.format(path=str(STUDIO), then=then)
    env = {**os.environ, "PRISM_SKIP_VENV_CHECK": "1"}
    return subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True
    ).returncode


def test_an_importer_keeps_its_exit_code():
    assert _run("sys.exit(3)") == 3


def test_an_importer_still_fails_on_an_uncaught_exception():
    assert _run("raise RuntimeError('boom')") == 1
