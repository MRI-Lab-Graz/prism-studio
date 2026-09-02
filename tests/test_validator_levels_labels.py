"""Unit tests for DatasetValidator._is_empty_levels_label.

Covers the dict-label branch directly, since the only prior coverage was
indirect (via _check_empty_levels_labels through a full validation run in
tests/test_multiversion_survey.py). These pin down every input the dead
ternary in that branch used to obscure: an all-None dict and an empty dict
both still route to "empty" once the ternary is collapsed to `return True`.
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from validator import DatasetValidator


def _validator() -> DatasetValidator:
    return DatasetValidator()


def test_none_label_is_empty():
    assert _validator()._is_empty_levels_label(None) is True


def test_blank_string_label_is_empty():
    assert _validator()._is_empty_levels_label("   ") is True


def test_nonempty_string_label_is_not_empty():
    assert _validator()._is_empty_levels_label("Male") is False


def test_empty_dict_label_is_empty():
    assert _validator()._is_empty_levels_label({}) is True


def test_dict_with_only_none_values_is_empty():
    assert _validator()._is_empty_levels_label({"en": None, "de": None}) is True


def test_dict_with_only_blank_string_values_is_empty():
    assert _validator()._is_empty_levels_label({"en": "", "de": "   "}) is True


def test_dict_with_nonempty_string_value_is_not_empty():
    assert _validator()._is_empty_levels_label({"en": "Male", "de": ""}) is False


def test_dict_with_non_string_non_none_value_is_not_empty():
    assert _validator()._is_empty_levels_label({"en": 5}) is False
