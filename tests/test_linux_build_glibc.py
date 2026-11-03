"""The Linux binary must run on Debian 12 (glibc 2.36); issue #212.

A PyInstaller binary needs the glibc of the machine that built it, so the
Linux build must not run on ubuntu-latest (24.04, glibc 2.39).
"""

from pathlib import Path

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build.yml"


def test_linux_build_runs_on_an_old_glibc_runner():
    text = WF.read_text(encoding="utf-8")
    block = text.split("platform_name: Linux")[0].rsplit("- os:", 1)[1]
    assert block.split()[0] == "ubuntu-22.04"
