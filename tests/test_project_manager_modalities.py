"""Regression guard for project_manager.py's PRISM_MODALITIES, which is now
derived from src/entity_rules.py instead of a hardcoded literal list.
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.project_manager import BIDS_PASSTHROUGH_MODALITIES, PRISM_MODALITIES


def test_prism_modalities_matches_previously_hardcoded_set():
    # Order is no longer guaranteed to match the old hardcoded list exactly
    # (nothing depends on it - see get_available_modalities() and its one
    # test, which mocks the function out entirely), so compare as a set.
    assert set(PRISM_MODALITIES) == {
        "survey", "biometrics", "environment", "physio", "eyetracking", "events",
    }


def test_bids_passthrough_modalities_unchanged():
    assert BIDS_PASSTHROUGH_MODALITIES == {"eyetracking"}


def test_prism_modalities_is_a_plain_list():
    assert isinstance(PRISM_MODALITIES, list)
