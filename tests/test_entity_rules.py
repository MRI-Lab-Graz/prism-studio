"""Regression guard for src/entity_rules.py.

The compiled regex/hint strings must be byte-identical to the hardcoded
constants they replace in app/src/validator.py and app/src/issues.py, so
this migration is a verified no-op rather than a "should behave the same"
hope.
"""

from __future__ import annotations

from src.entity_rules import (
    compile_modality_regex,
    describe_modality_pattern,
    load_entity_rules,
)

# Copied verbatim from app/src/validator.py's MODALITY_PATTERNS as it stood
# before the entities.json migration.
_EXPECTED_PATTERNS = {
    "survey": r".+_survey\.(tsv|json)$",
    "biometrics": r".+_biometrics\.(tsv|json)$",
    "environment": r".+_recording-[a-zA-Z0-9]+_environment\.(tsv|tsv\.gz|json)$",
    "events": r".+_events\.tsv$",
    "physio": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
    "physiological": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
    "eyetracking": r".+(_trackedEye-(left|right|both))?_(eyetrack|eye|gaze)\.(tsv|tsv\.gz|json|edf|asc)$",
}

# Copied verbatim from app/src/issues.py's get_fix_hint() modality_hints dict.
_EXPECTED_HINTS = {
    "survey": "Ensure the filename ends with '_survey.tsv' or '_survey.json' (e.g., sub-001_task-panas_survey.tsv)",
    "biometrics": "Ensure the filename ends with '_biometrics.tsv' or '_biometrics.json' (e.g., sub-001_task-rest_biometrics.tsv)",
    "physio": "Ensure the filename ends with '_physio.<ext>' where <ext> is tsv, tsv.gz, json, or edf (e.g., sub-001_task-rest_recording-ecg_physio.tsv)",
    "physiological": "Ensure the filename ends with '_physio.<ext>' where <ext> is tsv, tsv.gz, json, or edf (e.g., sub-001_task-rest_recording-ecg_physio.tsv)",
    "eyetracking": "Ensure the filename ends with '_eyetrack.<ext>' or '_eye.<ext>' or '_gaze.<ext>' where <ext> is tsv, tsv.gz, json, edf, or asc (e.g., sub-001_task-rest_trackedEye-left_eyetrack.tsv)",
    "events": "Ensure the filename ends with '_events.tsv' (e.g., sub-001_task-rest_events.tsv)",
}

_EXPECTED_ENTITY_ORDER = (
    "sub", "ses", "task", "acq", "run", "rec", "dir", "echo", "ce", "part", "space", "desc",
)
_EXPECTED_REQUIRED_ENTITIES = frozenset({"sub", "task"})


def test_compiled_regex_matches_hardcoded_patterns():
    rules = load_entity_rules()
    for modality, expected in _EXPECTED_PATTERNS.items():
        rule = rules.modalities[modality]
        assert compile_modality_regex(rule) == expected, modality


def test_describe_modality_pattern_matches_hardcoded_hints():
    rules = load_entity_rules()
    for modality, expected in _EXPECTED_HINTS.items():
        rule = rules.modalities[modality]
        assert describe_modality_pattern(rule) == expected, modality


def test_entity_order_matches_hardcoded_constant():
    rules = load_entity_rules()
    assert rules.entity_order == _EXPECTED_ENTITY_ORDER


def test_default_required_entities_matches_hardcoded_constant():
    rules = load_entity_rules()
    assert rules.default_required_entities == _EXPECTED_REQUIRED_ENTITIES


def test_prism_modalities_matches_hardcoded_constant():
    rules = load_entity_rules()
    assert rules.prism_modalities == {
        "survey", "biometrics", "environment", "events", "physio", "physiological",
    }


def test_bids_modalities_matches_hardcoded_constant():
    rules = load_entity_rules()
    assert rules.bids_modalities == {
        "anat", "func", "fmap", "dwi", "eeg", "beh", "eyetracking",
    }


def test_pattern_for_unlisted_modality_falls_back_to_catch_all():
    rules = load_entity_rules()
    assert rules.pattern_for("anat") == r".*"
    assert rules.pattern_for("does-not-exist") == r".*"


def test_load_entity_rules_is_cached():
    assert load_entity_rules() is load_entity_rules()
