"""eye2bids is not on PyPI: it is an opt-in GitHub install, pinned to a commit, never part of a default install."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "requirements-eyetrack.txt"


def test_eye2bids_is_pinned_to_a_full_commit():
    lines = [l for l in FILE.read_text().splitlines() if l.strip() and not l.startswith("#")]
    assert len(lines) == 1
    assert re.fullmatch(
        r"eye2bids @ git\+https://github\.com/bids-standard/eye2bids\.git@[0-9a-f]{40}", lines[0]
    ), lines


def test_no_default_install_path_pulls_it_in():
    for name in ("requirements.txt", "requirements-runtime.txt", "requirements-optional.txt", "setup.py"):
        assert "eye2bids" not in (ROOT / name).read_text(), name
