from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.version_utils import is_newer_release_available, parse_release_version


def test_parse_release_version_accepts_v_prefix_and_partial_semver():
    assert parse_release_version("v1.13.0") == (1, 13, 0)
    assert parse_release_version("1.14") == (1, 14, 0)


def test_parse_release_version_rejects_unknown_and_non_semver_tags():
    assert parse_release_version("unknown") is None
    assert parse_release_version("release-candidate") is None


def test_is_newer_release_available_returns_true_for_newer_release():
    assert is_newer_release_available("1.13.0", "1.14.0") is True


def test_is_newer_release_available_returns_false_when_latest_is_same_or_older():
    assert is_newer_release_available("1.13.0", "1.13.0") is False
    assert is_newer_release_available("1.13.1", "1.13.0") is False


def test_is_newer_release_available_returns_false_for_unknown_versions():
    assert is_newer_release_available("unknown", "1.14.0") is False
    assert is_newer_release_available("1.13.0", "unknown") is False
