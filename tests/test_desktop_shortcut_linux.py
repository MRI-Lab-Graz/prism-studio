"""On Linux the launcher must land in the app menu (~/.local/share/applications), because GNOME
(Fedora Workstation) shows no Desktop icons and will not start .desktop files from a folder."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the shortcut script is macOS/Linux")
ROOT = Path(__file__).resolve().parent.parent


def _fake(path, body):
    path.write_text("#!/bin/bash\n" + body, newline="\n")
    path.chmod(0o755)


def _run(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts/setup").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/setup/create_desktop_shortcut.sh", repo / "scripts/setup")
    (repo / ".venv/bin").mkdir(parents=True)
    _fake(repo / ".venv/bin/python", "")
    b = tmp_path / "bin"
    b.mkdir()
    _fake(b / "uname", "echo Linux")
    _fake(b / "xdg-user-dir", "exit 1")
    _fake(b / "gio", "")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    out = subprocess.run(
        ["/bin/bash", str(repo / "scripts/setup/create_desktop_shortcut.sh")],
        env={"PATH": f"{b}:/usr/bin:/bin", "HOME": str(home)}, capture_output=True, text=True,
    )
    return out, home


def test_launcher_goes_to_the_app_menu_without_a_desktop_folder(tmp_path):
    out, home = _run(tmp_path)
    assert out.returncode == 0, out.stdout + out.stderr
    entry = home / ".local/share/applications/prism-studio.desktop"
    assert "Exec=" in entry.read_text()


def test_desktop_copy_is_still_made_when_the_folder_exists(tmp_path):
    (tmp_path / "home/Desktop").mkdir(parents=True)
    out, home = _run(tmp_path)
    assert out.returncode == 0, out.stdout + out.stderr
    assert (home / ".local/share/applications/prism-studio.desktop").is_file()
    assert (home / "Desktop/prism-studio.desktop").is_file()
