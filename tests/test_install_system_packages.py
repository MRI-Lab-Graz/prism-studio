"""install.sh must offer one sudo command that installs every OS package a
standard Linux user lacks (tkinter folder picker, git, curl), not just warn."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="install.sh is macOS/Linux")
ROOT = Path(__file__).resolve().parent.parent


def _fake(path, body):
    path.write_text("#!/bin/bash\n" + body, newline="\n")
    path.chmod(0o755)


def _run(tmp_path, answer, pm="apt-get", has_git=False):
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    _fake(b / pm, "")
    _fake(b / "python3", "exit 1")  # import tkinter fails
    _fake(b / "sudo", f'echo "$@" >> {tmp_path}/ran')
    _fake(b / "uname", "echo Linux")
    if has_git:
        _fake(b / "git", "")
    funcs = subprocess.run(
        ["sed", "-n", "/^detect_package_manager()/,/^}/p;/^ensure_system_packages()/,/^}/p", "install.sh"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    script = f'echo_info() {{ echo "$1"; }}; echo_success() {{ :; }}; echo_error() {{ echo "$1"; }}\nid() {{ echo 1000; }}\n{funcs}\nensure_system_packages'
    return subprocess.run(
        ["/bin/bash", "-c", script], input=answer,
        env={"PATH": str(b)}, capture_output=True, text=True,
    )


def test_installs_missing_packages_in_one_sudo_call(tmp_path):
    out = _run(tmp_path, "y\n")
    assert out.returncode == 0, out.stdout + out.stderr
    ran = (tmp_path / "ran").read_text()
    assert "apt-get install -y python3-tk git curl" in ran


def test_only_missing_packages_are_requested(tmp_path):
    _run(tmp_path, "y\n", has_git=True)
    assert "python3-tk curl" in (tmp_path / "ran").read_text()
    assert "git" not in (tmp_path / "ran").read_text()


def test_declining_runs_nothing_and_prints_command(tmp_path):
    out = _run(tmp_path, "n\n")
    assert out.returncode == 0
    assert not (tmp_path / "ran").exists()
    assert "sudo apt-get install -y python3-tk git curl" in out.stdout


def test_dnf_uses_fedora_package_names(tmp_path):
    _run(tmp_path, "y\n", pm="dnf")
    assert "dnf install -y python3-tkinter git curl" in (tmp_path / "ran").read_text()
