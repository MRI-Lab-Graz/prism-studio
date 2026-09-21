"""Guards the symlinks that collapse the src/ vs app/src/ mirror pairs.

CLAUDE.md's fix for dual-tree drift is a real symlink on the ``src/`` side.
Git for Windows checks symlinks out as plain text files containing the target
path unless ``core.symlinks`` is enabled, which turns
``import src.converters.excel_base`` into a bare ``SyntaxError`` pointing at a
file that looks fine in an editor. This turns that into one readable failure.

Deliberately generic: it guards every symlink git tracks, so a future mirror
collapse is covered without touching this file.
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


def test_tracked_symlinks_are_usable_on_this_checkout():
    broken = {}
    for relative_path in _tracked_symlinks():
        path = REPO_ROOT / relative_path
        if not path.is_symlink():
            broken[relative_path] = (
                "checked out as a regular file (Windows without core.symlinks): "
                "Python will fail to parse the target path as source"
            )
        elif not path.resolve().is_file():
            broken[relative_path] = f"dangling, points at {path.resolve()}"

    assert not broken, "Unusable symlinks in this checkout: " + "; ".join(
        f"{name} - {reason}" for name, reason in sorted(broken.items())
    )
