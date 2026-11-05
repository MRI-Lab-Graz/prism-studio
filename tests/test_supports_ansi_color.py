"""Terminal colour detection: Windows consoles never set TERM, so TERM must not gate colour there."""

import os
import sys
import types

app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src import cross_platform


class _Tty:
    def __init__(self, tty=True):
        self._tty = tty

    def isatty(self):
        return self._tty


def test_windows_console_without_term_gets_color(monkeypatch):
    monkeypatch.setattr(cross_platform, "_enable_windows_vt", lambda: True)
    assert cross_platform.supports_ansi_color(_Tty(), {}, "nt") is True


def test_windows_console_that_refuses_vt_gets_no_color(monkeypatch):
    monkeypatch.setattr(cross_platform, "_enable_windows_vt", lambda: False)
    assert cross_platform.supports_ansi_color(_Tty(), {}, "nt") is False


def test_posix_needs_term():
    assert cross_platform.supports_ansi_color(_Tty(), {"TERM": "xterm"}, "posix") is True
    assert cross_platform.supports_ansi_color(_Tty(), {}, "posix") is False
    assert cross_platform.supports_ansi_color(_Tty(), {"TERM": "dumb"}, "posix") is False


def test_no_color_and_pipes_win(monkeypatch):
    monkeypatch.setattr(cross_platform, "_enable_windows_vt", lambda: True)
    assert cross_platform.supports_ansi_color(_Tty(), {"NO_COLOR": "1"}, "nt") is False
    assert cross_platform.supports_ansi_color(_Tty(False), {}, "nt") is False
    assert cross_platform.supports_ansi_color(None, {}, "nt") is False
