"""Tests for DatasetValidator._check_allowed_values.

These lock in behavior after consolidating three independently-drifted
implementations of "resolve allowed values from a column definition" (see
CLAUDE.md's dual-tree note) onto one canonical function
(app/src/converters/survey_core.py::get_allowed_values). The validator used
to carry its own private copy of this logic; this file exists so a future
refactor can't silently regress it back to the weaker behavior that used to
live in the other two copies (e.g. returning None — and skipping the check
entirely — for a Levels column with non-numeric keys).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from validator import DatasetValidator


def _issue_levels(issues):
    return [level for level, _ in issues]


class TestCheckAllowedValuesLevels:
    def test_numeric_levels_rejects_out_of_range_value(self):
        validator = DatasetValidator()
        col_def = {"Levels": {"0": "Never", "1": "Rarely", "2": "Often"}}
        issues = validator._check_allowed_values("5", "mood01", col_def, "sub-01_survey.tsv", 2)
        assert _issue_levels(issues) == ["ERROR"]
        assert "not in allowed values" in issues[0][1]

    def test_numeric_levels_accepts_in_range_value(self):
        validator = DatasetValidator()
        col_def = {"Levels": {"0": "Never", "1": "Rarely", "2": "Often"}}
        issues = validator._check_allowed_values("1", "mood01", col_def, "sub-01_survey.tsv", 2)
        assert issues == []

    def test_non_numeric_levels_still_enforced_not_skipped(self):
        # Regression guard: this column must not silently accept anything.
        # A prior, now-removed implementation returned None for non-numeric
        # Levels keys, which made _check_allowed_values treat the column as
        # unrestricted (`if not allowed: return []`) instead of validating it.
        validator = DatasetValidator()
        col_def = {"Levels": {"low": "Low risk", "high": "High risk"}}
        issues = validator._check_allowed_values("medium", "risk01", col_def, "sub-01_survey.tsv", 3)
        assert _issue_levels(issues) == ["ERROR"]
        assert "'low', 'high'" in issues[0][1]

    def test_non_numeric_levels_accepts_valid_value(self):
        validator = DatasetValidator()
        col_def = {"Levels": {"low": "Low risk", "high": "High risk"}}
        issues = validator._check_allowed_values("low", "risk01", col_def, "sub-01_survey.tsv", 3)
        assert issues == []

    def test_explicit_min_max_widens_allowed_range_beyond_level_keys(self):
        validator = DatasetValidator()
        col_def = {
            "Levels": {"0": "Not at all", "10": "Completely"},
            "MinValue": 0,
            "MaxValue": 10,
        }
        # 7 isn't a Levels key, but is within the declared MinValue/MaxValue range.
        issues = validator._check_allowed_values("7", "distress01", col_def, "sub-01_survey.tsv", 4)
        assert issues == []

    def test_numeric_normalization_accepts_float_form_of_int(self):
        validator = DatasetValidator()
        col_def = {"Levels": {"0": "Never", "1": "Rarely", "2": "Often"}}
        issues = validator._check_allowed_values("2.0", "mood01", col_def, "sub-01_survey.tsv", 2)
        assert issues == []

    def test_no_levels_or_allowed_values_skips_check(self):
        validator = DatasetValidator()
        col_def = {"Description": "free text field"}
        issues = validator._check_allowed_values("anything goes", "notes01", col_def, "sub-01_survey.tsv", 5)
        assert issues == []
