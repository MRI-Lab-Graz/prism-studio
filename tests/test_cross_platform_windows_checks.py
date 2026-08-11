"""Regression tests for the Windows symlink-support and long-path-enabled
detection helpers used by the DataLad/git-annex preflight status.

Both helpers must return None off Windows, and must never raise -- any
failure to determine the real state on Windows itself (missing winreg key,
permission denied, symlink creation denied) is treated as the cautious
"not confirmed" / False case rather than assumed safe.
"""

import os
import sys
import types

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src import cross_platform


def _fake_winreg(value, *, missing_key=False):
    fake = types.ModuleType("winreg")
    fake.HKEY_LOCAL_MACHINE = object()

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    def _open_key(hive, subkey):
        if missing_key:
            raise FileNotFoundError("registry key not found")
        return _Key()

    def _query_value_ex(key, name):
        return (value, 4)

    fake.OpenKey = _open_key
    fake.QueryValueEx = _query_value_ex
    return fake


def test_windows_symlinks_supported_none_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cross_platform.windows_symlinks_supported() is None


def test_windows_symlinks_supported_true_when_symlink_creation_succeeds(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert cross_platform.windows_symlinks_supported() is True


def test_windows_symlinks_supported_false_when_symlink_creation_denied(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    def _raise_symlink(*args, **kwargs):
        raise OSError("privilege not held")

    monkeypatch.setattr(os, "symlink", _raise_symlink)
    assert cross_platform.windows_symlinks_supported() is False


def test_windows_long_paths_enabled_none_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cross_platform.windows_long_paths_enabled() is None


def test_windows_long_paths_enabled_true(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", _fake_winreg(1))
    assert cross_platform.windows_long_paths_enabled() is True


def test_windows_long_paths_enabled_false_when_registry_value_zero(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", _fake_winreg(0))
    assert cross_platform.windows_long_paths_enabled() is False


def test_windows_long_paths_enabled_false_when_key_missing(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", _fake_winreg(0, missing_key=True))
    assert cross_platform.windows_long_paths_enabled() is False


def test_windows_long_paths_enabled_false_when_winreg_unavailable(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", None)
    assert cross_platform.windows_long_paths_enabled() is False
