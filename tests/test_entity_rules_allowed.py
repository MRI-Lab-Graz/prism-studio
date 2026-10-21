import pytest

from src.entity_rules import ModalityRule, check_entities, load_entity_rules

ORDER = ("sub", "ses", "task", "acq", "run", "rec")
ALLOWED = ("task", "acq", "run")


def _msgs(base):
    return check_entities(base, ALLOWED, ORDER)


def test_rule_reads_allowed_entities():
    rule = ModalityRule.from_json(
        "x", {"kind": "prism", "suffixes": ["x"], "extensions": ["tsv"], "allowedEntities": ["task", "acq"]}
    )
    assert rule.allowed_entities == ("task", "acq")


def test_rule_without_the_key_has_none():
    rule = ModalityRule.from_json("x", {"kind": "prism", "suffixes": ["x"], "extensions": ["tsv"]})
    assert rule.allowed_entities is None


def test_existing_modalities_have_no_allowed_entities_yet():
    rules = load_entity_rules()
    existing = ["survey", "biometrics", "environment", "events", "eyetracking"]
    assert all(rules.modalities[name].allowed_entities is None for name in existing)


@pytest.mark.parametrize(
    "base",
    [
        "sub-01_bloodchem",  # task is optional
        "sub-01_ses-pre_bloodchem",
        "sub-01_task-x_acq-fasting_run-2_bloodchem",
        "sub-01_task-bfi-s_bloodchem",  # hyphenated label is one value, not an entity
    ],
)
def test_valid_names_pass(base):
    assert _msgs(base) == []


def test_foreign_entity_is_reported():
    assert "'foo'" in " ".join(_msgs("sub-01_foo-1_bloodchem"))


def test_wrong_order_is_reported():
    assert "order" in " ".join(_msgs("sub-01_acq-a_task-x_bloodchem"))


def test_duplicate_entity_is_reported():
    assert "twice" in " ".join(_msgs("sub-01_run-1_run-2_bloodchem"))
