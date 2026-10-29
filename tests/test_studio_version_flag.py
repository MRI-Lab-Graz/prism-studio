"""`prism-studio.py -v` prints the version and where it runs from, without starting a server."""

import subprocess
import sys
from pathlib import Path

import pytest

from src import __version__

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("flag", ["-v", "--version"])
def test_version_flag_prints_version_and_install_path(flag):
    result = subprocess.run(
        [sys.executable, str(ROOT / "app" / "prism-studio.py"), flag],
        capture_output=True, text=True, timeout=120, cwd=ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == f"PRISM Studio {__version__} ({ROOT})"


def test_startup_banner_shows_the_version(tmp_path):
    import socket
    import time

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "app" / "prism-studio.py"), "--no-browser",
         "--no-dedicated-terminal", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT,
        env={**__import__("os").environ, "HOME": str(tmp_path)},
    )
    try:
        lines, deadline = [], time.time() + 90
        for line in server.stdout:
            lines.append(line.rstrip())
            if "Status: ready" in line or time.time() > deadline:
                break
    finally:
        server.terminate()
        server.wait(timeout=30)

    assert f"Version: {__version__} ({ROOT})" in lines
