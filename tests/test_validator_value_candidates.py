"""Unit tests for validator._value_candidates, the shared helper that
resolve_sidecar_path and _find_inherited_root_sidecar both use to build
acq-qualified sidecar name candidates."""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from validator import _value_candidates


def test_with_acq_value_prepends_acq_qualified_variant():
    assert _value_candidates("bfi", "s") == ["bfi_acq-s", "bfi"]


def test_without_acq_value_returns_base_only():
    assert _value_candidates("bfi", None) == ["bfi"]


def test_empty_base_value_returns_empty_list():
    assert _value_candidates("", "s") == []
    assert _value_candidates(None, "s") == []
