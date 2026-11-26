"""Biometrics measures are shared terms: the shipped template's columns name them, nothing is modality-specific."""

import json
from pathlib import Path

from src.mappings_coverage import coverage
from src.specification import current_specification
from src.term_registry import resolve_column, term_columns

TEMPLATE = Path(__file__).resolve().parents[1] / "official" / "library" / "biometrics" / "biometrics-fitness.json"


def test_every_column_of_the_fitness_template_resolves_to_its_term():
    sidecar = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    registry = current_specification().terms["biometrics"]
    columns = term_columns(sidecar, "biometrics")
    assert len(columns) == 8
    for name, definition in columns:
        found = resolve_column(registry, name, definition, None)
        assert found.kind == "term", (name, found.message)
        assert name in found.term.get("Aliases", []) or name == found.term["TermID"].split(":")[1]


def test_coverage_counts_biometrics_like_any_term_modality():
    spec = current_specification()
    assert coverage({"biometrics": spec.terms["biometrics"]}, spec.mappings_for)["biometrics"]["total"] == 11  # with height and weight
