"""Regression test for CrossPlatformFile.write_text: must retry through a
transient Windows antivirus lock on the atomic replace, and must never leave
a corrupted/partial file behind.

Windows Defender/AV frequently holds a brief exclusive lock on a just-written
file, surfacing as PermissionError (WinError 32) on os.replace() even though
nothing in PRISM itself still has the file open. This is the same failure
mode fixed for DatasetFixer renames (see app/src/fixer.py); project.json and
every other text file this app writes (README, CITATION.cff, .gitattributes,
etc.) go through this one shared function, so hardening it here fixes all of
them at once.
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.cross_platform import CrossPlatformFile  # noqa: E402
import src.cross_platform as cross_platform  # noqa: E402


def test_write_text_writes_correct_content(tmp_path):
    target = tmp_path / "project.json"
    CrossPlatformFile.write_text(str(target), '{"a": 1}')
    assert target.read_text(encoding="utf-8") == '{"a": 1}'


def test_write_text_leaves_no_leftover_temp_file(tmp_path):
    target = tmp_path / "project.json"
    CrossPlatformFile.write_text(str(target), "content")
    assert list(tmp_path.iterdir()) == [target]


def test_write_text_retries_through_transient_permission_error(tmp_path, monkeypatch):
    target = tmp_path / "project.json"

    real_replace = os.replace
    calls = {"count": 0}

    def _flaky_replace(src, dst):
        calls["count"] += 1
        if calls["count"] < 3:
            raise PermissionError("[WinError 32] file in use")
        real_replace(src, dst)

    monkeypatch.setattr(cross_platform.os, "replace", _flaky_replace)
    monkeypatch.setattr(cross_platform.time, "sleep", lambda seconds: None)

    CrossPlatformFile.write_text(str(target), "recovered content")

    assert target.read_text(encoding="utf-8") == "recovered content"
    assert calls["count"] == 3
    assert list(tmp_path.iterdir()) == [target]


def test_write_text_raises_and_cleans_up_after_persistent_lock(tmp_path, monkeypatch):
    target = tmp_path / "project.json"

    def _always_locked(src, dst):
        raise PermissionError("[WinError 32] file in use")

    monkeypatch.setattr(cross_platform.os, "replace", _always_locked)
    monkeypatch.setattr(cross_platform.time, "sleep", lambda seconds: None)

    try:
        CrossPlatformFile.write_text(str(target), "content")
        assert False, "expected PermissionError to propagate"
    except PermissionError:
        pass

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
