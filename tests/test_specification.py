"""src/specification.py: what the validator knows (modalities, schemas, terms) as one object, current per run."""

import json
import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.entity_rules import load_entity_rules  # noqa: E402
from src.schema_manager import DEFAULT_SCHEMA_DIR, load_all_schemas  # noqa: E402
from src.specification import (  # noqa: E402
    Specification, current_specification, load_specification, official_specification, use_specification,
)

REPO = Path(__file__).resolve().parents[1]


def stand_in(tmp_path: Path) -> Specification:
    """A specification with one extra modality, built from a temporary copy of the entity rules."""
    stable = tmp_path / "stable"
    stable.mkdir(parents=True)
    data = json.loads((REPO / "app" / "schemas" / "stable" / "entities.schema.json").read_text(encoding="utf-8"))
    data["modalities"]["skinconductance"] = {"kind": "prism", "suffixes": ["skinconductance"], "extensions": ["tsv", "json"]}
    (stable / "entities.schema.json").write_text(json.dumps(data), encoding="utf-8")
    return load_specification(rules=load_entity_rules(str(tmp_path)))


def test_outside_a_run_the_official_specification_is_current():
    assert current_specification() is official_specification()
    assert "biosample" in current_specification().rules.prism_modalities
    assert "skinconductance" not in current_specification().rules.prism_modalities


def test_use_specification_sets_and_resets(tmp_path):
    spec = stand_in(tmp_path)
    with use_specification(spec) as inside:
        assert inside is spec and current_specification() is spec
    assert current_specification() is official_specification()


def test_use_specification_resets_after_an_exception(tmp_path):
    spec = stand_in(tmp_path)
    with pytest.raises(RuntimeError):
        with use_specification(spec):
            raise RuntimeError("boom")
    assert current_specification() is official_specification()


def test_nested_use_restores_the_outer_one(tmp_path):
    outer, inner = stand_in(tmp_path / "a"), stand_in(tmp_path / "b")
    with use_specification(outer):
        with use_specification(inner):
            assert current_specification() is inner
        assert current_specification() is outer


def test_a_new_thread_starts_with_the_official_specification(tmp_path):
    seen = []
    with use_specification(stand_in(tmp_path)):
        worker = threading.Thread(target=lambda: seen.append(current_specification()))
        worker.start()
        worker.join()
    assert len(seen) == 1 and seen[0] is official_specification()


def test_load_specification_matches_what_the_runner_loads_today():
    spec = load_specification()
    assert spec.schemas == load_all_schemas(DEFAULT_SCHEMA_DIR)
    assert spec.rules is load_entity_rules()
    assert "cortisol.saliva" in spec.terms["biosample"]


def test_the_stand_in_has_its_extra_modality(tmp_path):
    spec = stand_in(tmp_path)
    assert "skinconductance" in spec.rules.prism_modalities
    assert "skinconductance" not in official_specification().rules.prism_modalities


def test_derived_views_equal_the_frozen_constants_they_replace():
    """The official specification must answer exactly like the constants validator.py froze at import."""
    from validator import BIDS_MODALITIES, MODALITY_PATTERNS, PRISM_MODALITIES

    spec = official_specification()
    assert spec.prism_modalities == PRISM_MODALITIES
    assert spec.bids_modalities == BIDS_MODALITIES
    assert spec.modality_patterns == MODALITY_PATTERNS


def test_derived_views_follow_the_rules_of_a_stand_in(tmp_path):
    spec = stand_in(tmp_path)
    assert "skinconductance" in spec.prism_modalities and "skinconductance" in spec.modality_patterns
    assert "skinconductance" not in official_specification().modality_patterns


def test_a_specification_is_hashable_and_compared_by_identity(tmp_path):
    spec = stand_in(tmp_path)
    assert hash(spec) == hash(spec)  # dict fields made the generated __hash__ raise TypeError
    assert spec != load_specification(rules=spec.rules)  # same content, different object: no deep dict comparison


def test_the_specification_exposes_the_described_columns_set():
    assert official_specification().described_columns == {"survey", "biometrics", "biosample", "environment"}


def test_specification_loads_environment_terms():
    from src.specification import load_specification

    spec = load_specification()
    assert "air-temperature" in spec.terms["environment"]
    assert set(spec.term_modalities) == {"biosample", "environment"}
