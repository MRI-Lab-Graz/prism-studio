"""Run the PyPI validator the way a user gets it: only the files the wheel build stages."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stage_wheel(dest: Path) -> Path:
    """Stage like scripts/build_validator_wheel.py; returns the staged prism.py."""
    spec = importlib.util.spec_from_file_location("build_validator_wheel", ROOT / "scripts" / "build_validator_wheel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.stage(dest)
    return dest / "prism_validator" / "app" / "prism.py"


def run_validator(prism: Path, dataset: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(prism), str(dataset), "--no-bids", *args],
        capture_output=True, text=True, timeout=300, cwd=cwd,
        env={"PATH": "/usr/bin:/bin", "PRISM_SKIP_VENV_CHECK": "1", "HOME": str(cwd)},
    )
