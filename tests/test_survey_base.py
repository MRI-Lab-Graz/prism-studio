"""Tests for the shared survey library helpers (canonical implementation lives
in app/src/converters/survey_core.py; src.converters.survey_base re-exports
it — see CLAUDE.md's dual-tree note).
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.survey_base import load_survey_library, get_allowed_values


# ---------------------------------------------------------------------------
# load_survey_library
# ---------------------------------------------------------------------------

class TestLoadSurveyLibrary:
    def test_missing_path_returns_empty(self, tmp_path):
        result = load_survey_library(str(tmp_path / "nonexistent"))
        assert result == {}

    def test_loads_survey_json(self, tmp_path):
        data = {"name": "PHQ-9", "items": []}
        (tmp_path / "survey-phq9.json").write_text(json.dumps(data))
        result = load_survey_library(str(tmp_path))
        assert "phq9" in result
        assert result["phq9"]["name"] == "PHQ-9"

    def test_ignores_non_survey_prefix(self, tmp_path):
        (tmp_path / "template-foo.json").write_text("{}")
        result = load_survey_library(str(tmp_path))
        assert result == {}

    def test_ignores_invalid_json(self, tmp_path):
        (tmp_path / "survey-bad.json").write_text("not json {{")
        result = load_survey_library(str(tmp_path))
        assert result == {}

    def test_multiple_surveys_loaded(self, tmp_path):
        for name in ["phq9", "gad7", "bdi"]:
            (tmp_path / f"survey-{name}.json").write_text(json.dumps({"name": name}))
        result = load_survey_library(str(tmp_path))
        assert set(result.keys()) == {"phq9", "gad7", "bdi"}


# ---------------------------------------------------------------------------
# get_allowed_values
# ---------------------------------------------------------------------------

class TestGetAllowedValues:
    def test_returns_none_for_non_dict(self):
        assert get_allowed_values("just a string") is None
        assert get_allowed_values(None) is None
        assert get_allowed_values(42) is None

    def test_allowed_values_list(self):
        col = {"AllowedValues": [1, 2, 3]}
        result = get_allowed_values(col)
        assert result == ["1", "2", "3"]

    def test_levels_numeric_range(self):
        col = {"Levels": {"1": "Never", "2": "Sometimes", "3": "Often"}}
        result = get_allowed_values(col)
        assert result == ["1", "2", "3"]

    def test_levels_non_numeric_keys_are_preserved(self):
        # Non-numeric level keys can't form a range, but the check must still
        # run against the raw keys rather than silently returning None (which
        # would make _check_allowed_values skip validation for this column
        # entirely — that was a real bug, not intended behavior; see
        # CLAUDE.md's dual-tree note for how this drifted across three
        # independent implementations before being consolidated here).
        col = {"Levels": {"low": "Low", "high": "High"}}
        result = get_allowed_values(col)
        assert result == ["low", "high"]

    def test_levels_mixed_numeric_and_non_numeric_keys(self):
        col = {"Levels": {"1": "One", "2": "Two", "3": "Three", "na": "Not applicable"}}
        result = get_allowed_values(col)
        assert result == ["1", "2", "3", "na"]

    def test_levels_large_range_returns_keys(self):
        col = {"Levels": {str(i): str(i) for i in range(200)}}
        result = get_allowed_values(col)
        # range >= 100 → returns raw keys, not an expanded 0..199 range
        assert len(result) == 200

    def test_levels_binary_range_returns_keys_unexpanded(self):
        # A 2-level range (max - min == 1) is below the expansion threshold;
        # returning the raw keys is equivalent here (there's nothing to fill
        # in between 0 and 1) but exercises the boundary condition directly.
        col = {"Levels": {"0": "No", "1": "Yes"}}
        result = get_allowed_values(col)
        assert result == ["0", "1"]

    def test_levels_with_explicit_min_max_uses_those_bounds_not_level_keys(self):
        # MinValue/MaxValue take precedence over the Levels dict's own keys —
        # e.g. a template documenting only the endpoints of a 0-10 scale.
        col = {"Levels": {"0": "Not at all", "10": "Completely"}, "MinValue": 0, "MaxValue": 10}
        result = get_allowed_values(col)
        assert result == [str(i) for i in range(11)]

    def test_levels_with_unparseable_min_max_falls_back_to_level_keys(self):
        col = {"Levels": {"0": "No", "1": "Yes"}, "MinValue": "n/a", "MaxValue": "n/a"}
        result = get_allowed_values(col)
        assert result == ["0", "1"]

    def test_no_allowed_values_or_levels(self):
        assert get_allowed_values({"Description": "some field"}) is None

    def test_allowed_values_not_a_list_falls_back_to_levels(self):
        # A malformed AllowedValues (e.g. a stray string) must not crash or
        # be iterated character-by-character — fall back to Levels instead.
        col = {"AllowedValues": "not-a-list", "Levels": {"0": "No", "1": "Yes"}}
        result = get_allowed_values(col)
        assert result == ["0", "1"]

    def test_allowed_values_takes_precedence_over_levels(self):
        col = {"AllowedValues": [0, 1], "Levels": {"0": "No", "1": "Yes", "2": "Maybe"}}
        result = get_allowed_values(col)
        assert result == ["0", "1"]
