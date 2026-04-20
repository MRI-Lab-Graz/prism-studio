from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRISM_STUDIO_WRAPPER = PROJECT_ROOT / "prism-studio.py"
SETTINGS_PATH = PROJECT_ROOT / "app" / "prism_studio_settings.json"


def _restore_settings_file(
    original_content: str | None, originally_present: bool
) -> None:
    if originally_present:
        if original_content is not None:
            SETTINGS_PATH.write_text(original_content, encoding="utf-8")
        return

    if SETTINGS_PATH.exists():
        SETTINGS_PATH.unlink()


def test_prism_studio_wrapper_help_skips_repo_venv_bootstrap_when_requested() -> None:
    original_content = None
    originally_present = SETTINGS_PATH.exists()
    if originally_present:
        original_content = SETTINGS_PATH.read_text(encoding="utf-8")

    env = os.environ.copy()
    env["PRISM_SKIP_VENV_CHECK"] = "1"
    env.pop("CI", None)

    try:
        result = subprocess.run(
            [sys.executable, str(PRISM_STUDIO_WRAPPER), "--help", "--no-browser"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=30,
            env=env,
        )
    finally:
        _restore_settings_file(original_content, originally_present)

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert "--no-browser" in output
