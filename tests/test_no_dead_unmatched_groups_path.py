"""Guard: the blocking 'unmatched groups' (409) path was removed; keep it gone."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def test_unmatched_groups_error_is_gone():
    survey = importlib.import_module("src.converters.survey")
    assert not hasattr(survey, "UnmatchedGroupsError")


def test_format_unmatched_groups_response_is_gone():
    helpers = importlib.import_module(
        "src.web.blueprints.conversion_survey_response_helpers"
    )
    assert not hasattr(helpers, "format_unmatched_groups_response")
