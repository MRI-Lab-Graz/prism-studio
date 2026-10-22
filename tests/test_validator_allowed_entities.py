import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import validator as v  # noqa: E402
from src.entity_rules import ModalityRule  # noqa: E402
from src.specification import load_specification, official_specification, use_specification  # noqa: E402


@pytest.fixture
def strict_modality():
    """A modality with allowedEntities, as a specification of its own: the shared official rules are not touched."""
    rule = ModalityRule.from_json(
        "bloodtest",
        {"kind": "prism", "suffixes": ["bloodchem"], "extensions": ["tsv", "json"],
         "allowedEntities": ["task", "acq", "run"]},
    )
    rules = official_specification().rules
    rules = dataclasses.replace(rules, modalities={**rules.modalities, "bloodtest": rule})
    with use_specification(load_specification(rules=rules)):
        yield


def _errors(name):
    issues = v.DatasetValidator().validate_filename(name, "bloodtest", subject_id="sub-01")
    return [m for level, m in issues if level == "ERROR"]


def test_task_is_optional(strict_modality):
    assert _errors("sub-01_bloodchem.tsv") == []
    assert _errors("sub-01_acq-fasting_bloodchem.tsv") == []


def test_foreign_entity_is_an_error(strict_modality):
    assert any("'foo'" in m for m in _errors("sub-01_foo-1_bloodchem.tsv"))


def test_modalities_without_the_key_are_unchanged():
    issues = v.DatasetValidator().validate_filename(
        "sub-01_foo-1_task-x_biometrics.tsv", "biometrics", subject_id="sub-01"
    )
    assert not any("not allowed" in m for _, m in issues)
