"""A commit message may start with "-" ("- first fix", "--wip"); it must not be read as an option."""

import shutil
import subprocess

import pytest

from src.datalad_execution import run_datalad_save

pytestmark = pytest.mark.skipif(
    not (shutil.which("datalad") and shutil.which("git-annex")), reason="datalad and git-annex are not installed"
)


@pytest.mark.parametrize("message", ["- first fix", "--wip", "-m", "-x", "plain"])
def test_save_message_starting_with_a_dash_is_the_message(tmp_path, message):
    subprocess.run(["datalad", "create", "--no-annex", str(tmp_path / "ds")], check=True, capture_output=True)
    root = tmp_path / "ds"
    (root / "file.txt").write_text("x")

    result = run_datalad_save(root, message=message)

    assert result["success"], result
    log = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%s"], capture_output=True, text=True).stdout.strip()
    assert log == message
