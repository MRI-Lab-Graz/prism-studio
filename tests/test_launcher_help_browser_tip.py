"""The browser tip lives in `prism-studio.py -h`, not in the startup banner every launch prints."""

import subprocess
import sys
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "app" / "prism-studio.py"


def test_the_browser_tip_is_in_the_help_and_not_in_the_startup_banner():
    assert "Chromium-based browser" not in LAUNCHER.read_text(encoding="utf-8").split("def _print_startup_ready")[1].split("_print_startup_intro()")[0]
    help_text = subprocess.run([sys.executable, str(LAUNCHER), "-h"], capture_output=True, text=True, timeout=60).stdout
    assert "Chromium-based browser" in help_text
