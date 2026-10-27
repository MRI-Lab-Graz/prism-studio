"""Regression guard for src/entity_rules.py.

The compiled regex/hint strings must be byte-identical to the hardcoded
constants they replace in app/src/validator.py and app/src/issues.py, so
this migration is a verified no-op rather than a "should behave the same"
hope.
"""

from __future__ import annotations

from src.entity_rules import (
    ModalityRule,
    compile_modality_regex,
    describe_modality_pattern,
    load_entity_rules,
)

# Copied verbatim from app/src/validator.py's MODALITY_PATTERNS as it stood
# before the entities.json migration.
_EXPECTED_PATTERNS = {
    "survey": r".+_task-[a-zA-Z0-9-]+(_acq-([a-zA-Z0-9-]+))?(_run-([a-zA-Z0-9]+))?_survey\.(tsv|json)$",  # task required since 2026-10-24
    "biometrics": r".+_biometrics\.(tsv|json)$",
    "biosample": r".+_biosample\.(tsv|json)$",
    "environment": r".+_recording-[a-zA-Z0-9]+_environment\.(tsv|tsv\.gz|json)$",
    "events": r".+_events\.tsv$",
    "physio": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
}

# Copied verbatim from app/src/issues.py's get_fix_hint() modality_hints dict.
_EXPECTED_HINTS = {
    "survey": "Ensure the filename ends with '_survey.tsv' or '_survey.json' (e.g., sub-001_task-panas_survey.tsv)",
    "biometrics": "Ensure the filename ends with '_biometrics.tsv' or '_biometrics.json' (e.g., sub-001_task-rest_biometrics.tsv)",
    "physio": "Ensure the filename ends with '_physio.<ext>' where <ext> is tsv, tsv.gz, json, or edf (e.g., sub-001_task-rest_recording-ecg_physio.tsv)",
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
        "survey", "biometrics", "biosample", "environment", "events", "physio",
    }


def test_bids_modalities_matches_hardcoded_constant():
    rules = load_entity_rules()
    assert rules.bids_modalities == {
        "anat", "func", "fmap", "dwi", "eeg", "beh",
    }


def test_pattern_for_unlisted_modality_falls_back_to_catch_all():
    rules = load_entity_rules()
    assert rules.pattern_for("anat") == r".*"
    assert rules.pattern_for("does-not-exist") == r".*"


def test_load_entity_rules_is_cached():
    assert load_entity_rules() is load_entity_rules()


def test_modalities_with_suffixes_matches_original_pattern_dict_keys():
    """validator.py's MODALITY_PATTERNS must only carry the 8 modalities the
    hardcoded dict used to have - not every entities.schema.json entry (e.g.
    bidsPassthrough modalities like anat/func with no suffix grammar of
    their own). Consumers like app/src/runner.py iterate this dict's keys
    directly, so an inflated key set would be a real behavior change even
    though nothing in this repo currently trips over it."""
    rules = load_entity_rules()
    modalities_with_suffixes = {
        name for name, rule in rules.modalities.items() if rule.suffixes
    }
    assert modalities_with_suffixes == set(_EXPECTED_PATTERNS.keys())


def test_project_modalities_matches_project_manager_hardcoded_list():
    """project_manager.py's PRISM_MODALITIES used to hardcode exactly these
    6 names (order differs, which is harmless - nothing depends on it)."""
    rules = load_entity_rules()
    assert set(rules.project_modalities) == {
        "survey", "biometrics", "biosample", "environment", "physio",
    }


def test_project_modalities_excludes_alias_and_bare_bids_passthrough():
    rules = load_entity_rules()
    assert "physiological" not in rules.modalities
    assert "anat" not in rules.project_modalities
    assert "func" not in rules.project_modalities


def test_prism_modalities_matches_bids_integration_prism_folders_intent():
    """bids_integration.py's prism_folders used to hardcode these 6 names
    (plus dead "eeg" and vestigial "metadata" entries, since removed)."""
    rules = load_entity_rules()
    assert rules.prism_modalities == {
        "survey", "biometrics", "biosample", "environment", "physio", "events",
    }


def test_biosample_is_registered_with_tsv_json_suffix():
    rules = load_entity_rules()
    rule = rules.modalities["biosample"]
    assert rule.kind == "prism"
    assert rule.suffixes == ("biosample",)
    assert rules.pattern_for("biosample") == r".+_biosample\.(tsv|json)$"


def test_physiological_alias_is_gone():
    assert load_entity_rules().aliases == {}


def test_events_is_not_a_project_folder():
    rules = load_entity_rules()
    assert "events" not in rules.project_modalities
    assert rules.modalities["events"].folder is False
    assert rules.modalities["physio"].folder is True


def test_physio_rejects_task():
    from src.entity_rules import check_entities

    rules = load_entity_rules()
    allowed = rules.modalities["physio"].allowed_entities
    assert allowed == ("acq", "run", "recording")
    assert check_entities("sub-01_task-x_recording-ecg_physio", allowed, rules.entity_order)
    assert check_entities("sub-01_ses-pre_recording-ecg", allowed, rules.entity_order) == []


def test_not_allowed_message_lists_every_permitted_entity():
    from src.entity_rules import check_entities

    rules = load_entity_rules()
    allowed = rules.modalities["physio"].allowed_entities
    (message,) = check_entities("sub-01_task-x_recording-ecg_physio", allowed, rules.entity_order)
    assert "recording" in message.split("allowed:")[1]


def test_events_pin_still_resolves():
    from src.modality_versions import modality_names

    assert "events" in modality_names()


def test_official_rules_describe_columns_of_exactly_these_modalities():
    assert load_entity_rules().described_columns_modalities == {
        "survey",
        "biometrics",
        "biosample",
        "environment",
    }


def test_a_rule_without_the_key_does_not_describe_columns():
    rule = ModalityRule.from_json("x", {"kind": "prism", "suffixes": ["x"], "extensions": ["tsv"]})
    assert rule.described_columns is False and rule.description == ""


def test_term_modalities_from_entities():
    assert load_entity_rules().term_modalities == {
        "biosample": {"nonTermColumns": ["sample_id", "collection_time", "fasting"], "contextField": "Technical.SpecimenType"},
        "environment": {"nonTermColumns": ["subject_id", "session_id"]},
    }
