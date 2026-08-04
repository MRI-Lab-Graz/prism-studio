"""Tests for the dormant fallback branches in app/src/web/utils.py.

`shorten_path`/`get_filename_from_path` normally delegate straight through to
the real implementation in `src.web.path_utils`. The fallback bodies here
only run if that import fails (e.g. a packaging gap in a frozen/PyInstaller
build — see the `if getattr(sys, "frozen", False)` branch in
app/prism-studio.py). Existing tests (test_web_formatting.py) exercise the
wrapper end-to-end but never actually reach these fallback bodies, since the
import always succeeds in a normal dev/test environment. This file forces
that branch directly so the safety net itself has coverage — it used to
silently disagree with the real implementation on both empty-path handling
and path-separator cross-platform correctness (hardcoded '/' instead of
os.sep) before being reconciled; see CLAUDE.md's dual-tree note.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web import utils as web_utils


def _disable_path_utils_delegation(monkeypatch):
    """Force shorten_path/get_filename_from_path onto their fallback bodies."""
    monkeypatch.setattr(web_utils, "_import_shorten_path", None)
    monkeypatch.setattr(web_utils, "_import_get_filename_from_path", None)


class TestShortenPathFallback:
    def test_empty_path_returns_general(self, monkeypatch):
        _disable_path_utils_delegation(monkeypatch)
        assert web_utils.shorten_path("") == "General"
        assert web_utils.shorten_path(None) == "General"

    def test_short_path_returned_unchanged(self, monkeypatch):
        _disable_path_utils_delegation(monkeypatch)
        path = os.sep.join(["sub-01", "file.tsv"])
        assert web_utils.shorten_path(path, max_parts=3) == path

    def test_long_path_truncated_with_native_separator(self, monkeypatch):
        _disable_path_utils_delegation(monkeypatch)
        parts = ["a", "b", "c", "d", "e"]
        path = os.sep.join(parts)
        result = web_utils.shorten_path(path, max_parts=3)
        assert result == "..." + os.sep + os.sep.join(parts[-3:])

    def test_backslash_input_normalized_to_native_separator(self, monkeypatch):
        # A Windows-style input path must not leak literal backslashes into
        # the output on a POSIX host, and must split into the same number
        # of parts a forward-slash path would.
        _disable_path_utils_delegation(monkeypatch)
        result = web_utils.shorten_path("a\\b\\c\\d\\e", max_parts=3)
        assert result == "..." + os.sep + os.sep.join(["c", "d", "e"])


class TestGetFilenameFromPathFallback:
    def test_empty_path_returns_general(self, monkeypatch):
        _disable_path_utils_delegation(monkeypatch)
        assert web_utils.get_filename_from_path("") == "General"
        assert web_utils.get_filename_from_path(None) == "General"

    def test_returns_basename(self, monkeypatch):
        _disable_path_utils_delegation(monkeypatch)
        path = os.path.join("a", "b", "file.tsv")
        assert web_utils.get_filename_from_path(path) == "file.tsv"


class TestEndpointExistsOutsideAppContext:
    def test_returns_false_without_flask_app_context(self):
        # No Flask app/request context is active in a plain pytest process,
        # so accessing current_app raises RuntimeError internally — that
        # must be swallowed and return False, not propagate.
        assert web_utils.endpoint_exists("anything.at_all") is False
