"""Without eol rules, Windows `autocrlf` checks shell scripts out as CRLF and sh refuses them."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _eol(path: str) -> str:
    out = subprocess.run(
        ["git", "check-attr", "eol", "--", path], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return out.strip().rsplit(": ", 1)[-1]


def test_unix_scripts_stay_lf_on_windows_checkouts():
    assert _eol("install.sh") == "lf"
    assert _eol("scripts/release/macos_first_run.command") == "lf"


def test_windows_scripts_stay_crlf():
    assert _eol("install.cmd") == "crlf"
    assert _eol("start.cmd") == "crlf"
