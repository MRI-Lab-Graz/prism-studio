"""verify_repo prints check marks; piped output on Windows is cp1252 and used to crash on them."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_repo_survives_a_non_utf8_pipe():
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONIOENCODING", "PYTHONUTF8"}}
    run = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "verify_repo.py"), "--check", "dual-tree-drift", "--no-fix"],
        capture_output=True, env=env, cwd=ROOT, timeout=300,
    )
    assert b"UnicodeEncodeError" not in run.stderr, run.stderr.decode("utf-8", "replace")
