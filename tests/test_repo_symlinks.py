"""The repo must not track symlinks.

Git for Windows (without Developer Mode / ``core.symlinks``) and GitHub's ZIP
download both check a symlink out as a plain text file containing the target
path. For the old ``src/`` -> ``app/src/`` mirror symlinks that turned
``import src.converters.excel_base`` into a bare ``SyntaxError``, so
install.cmd on a fresh Windows machine produced a Studio that would not start.

A module that lives in ``app/src/`` needs no ``src/`` stand-in: ``src``'s
``__path__`` falls through to ``app/src`` (see src/__init__.py), so
``src.<name>`` finds it either way.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _tracked_symlinks():
    """Paths git has at mode 120000, i.e. recorded as symlinks."""
    result = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line.split("\t", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("120000 ")
    ]


def test_repo_tracks_no_symlinks():
    assert _tracked_symlinks() == []


def test_former_mirror_modules_import_from_app_src():
    code = (
        "import src.converters.excel_base, src.converters.survey, "
        "src.converters.survey_base; print('ok')"
    )
    result = subprocess.run(
        [__import__("sys").executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
