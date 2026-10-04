"""The validator CLI must not build environment TSVs.

`prism.py --build-environment` used hash-derived placeholder values for
weather/pollen/air quality instead of real data. Environment enrichment is
`prism_tools.py environment convert` (src/environment_conversion.py) only.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validator_rejects_build_environment(tmp_path):
    out = tmp_path / "sub-01_environment.tsv"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "app" / "prism.py"),
            "--build-environment",
            "--scans-tsv",
            str(tmp_path / "scans.tsv"),
            "--environment-tsv",
            str(out),
            "--lat",
            "47",
            "--lon",
            "15",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
        env={**os.environ, "PRISM_SKIP_VENV_CHECK": "1"},
    )
    assert r.returncode == 2, r.stdout + r.stderr  # argparse: unknown option
    assert "unrecognized arguments" in r.stderr
    assert not out.exists()


def test_fake_environment_package_is_gone():
    assert not (ROOT / "app" / "src" / "environment").exists()
