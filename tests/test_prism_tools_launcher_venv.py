"""Root prism_tools.py re-execs into .venv like prism.py (launcher_exec.ensure_venv)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE_PYTHON = getattr(sys, "_base_executable", None)


@pytest.mark.skipif(
    not (ROOT / ".venv").is_dir() or not BASE_PYTHON or BASE_PYTHON == sys.executable,
    reason="needs a repo .venv and a separate base interpreter",
)
def test_prism_tools_from_outside_venv_reexecs_into_venv():
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PRISM_SKIP_VENV_CHECK", "CI", "VIRTUAL_ENV", "PYTHONPATH"}
    }
    r = subprocess.run(
        [BASE_PYTHON, str(ROOT / "prism_tools.py"), "--help"],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "usage:" in r.stdout
