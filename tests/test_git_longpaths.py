"""core.longpaths must be set on every dataset root, on Windows only.

git-annex object paths repeat the full SHA256E key as both a directory and the
filename inside it, which on top of normal BIDS nesting clears Windows'
260-character MAX_PATH limit easily. Git then fails mid-checkout with a
misleading "Filename too long".

Setting the flag is platform-gated, so both branches are forced here with
monkeypatch rather than depending on the host OS.
"""

import unittest.mock as mock
from pathlib import Path

import pytest

from src.project_manager import ProjectManager


@pytest.fixture
def manager():
    return ProjectManager()


def test_sets_core_longpaths_on_windows(manager, monkeypatch, tmp_path):
    monkeypatch.setattr("src.project_manager.sys.platform", "win32")

    with mock.patch("src.project_manager.subprocess.run") as run:
        manager._ensure_git_longpaths(tmp_path)

    run.assert_called_once()
    assert run.call_args.args[0] == [
        "git",
        "-C",
        str(tmp_path),
        "config",
        "core.longpaths",
        "true",
    ]


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_is_a_no_op_off_windows(manager, monkeypatch, tmp_path, platform):
    monkeypatch.setattr("src.project_manager.sys.platform", platform)

    with mock.patch("src.project_manager.subprocess.run") as run:
        manager._ensure_git_longpaths(tmp_path)

    run.assert_not_called()


def test_a_broken_git_does_not_break_dataset_setup(manager, monkeypatch, tmp_path):
    monkeypatch.setattr("src.project_manager.sys.platform", "win32")

    with mock.patch(
        "src.project_manager.subprocess.run", side_effect=OSError("git missing")
    ):
        manager._ensure_git_longpaths(tmp_path)  # must not raise


def test_policy_pass_configures_every_dataset_root(manager, monkeypatch, tmp_path):
    """The flag has to reach subdatasets too, not just the top-level dataset."""
    roots = [tmp_path, tmp_path / "sub-01", tmp_path / "derivatives"]
    for root in roots:
        root.mkdir(exist_ok=True)

    monkeypatch.setattr(
        manager, "_iter_datalad_dataset_roots", lambda _project_path: roots
    )
    monkeypatch.setattr(
        manager, "_derivatives_text_policy_extra_lines", lambda *_args: ()
    )
    monkeypatch.setattr(
        manager,
        "_ensure_datalad_editable_metadata_policy_for_root",
        lambda *_args, **_kwargs: False,
    )

    seen = []
    monkeypatch.setattr(manager, "_ensure_git_longpaths", seen.append)

    manager._ensure_datalad_editable_metadata_policy(Path(tmp_path))

    assert seen == roots
