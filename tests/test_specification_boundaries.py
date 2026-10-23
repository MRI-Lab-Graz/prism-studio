"""Validation code asks the current specification; it does not read constants frozen at import
or call load_entity_rules() itself (phase 0 of the specification contributions design).

A hand-written copy of "which modalities exist" is how `biosample` was forgotten in the BIDS folder list.
Module-level definitions of the official defaults stay (code without a project and the tests import them).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = {"_ENTITY_RULES", "PRISM_MODALITIES", "BIDS_MODALITIES", "MODALITY_PATTERNS"}
GUARDED = [
    "app/src/validator.py",
    "app/src/runner.py",
    "app/src/fixer.py",
    "app/src/project_manager.py",
    "app/src/bids_validator.py",
    "app/src/bids_integration.py",
    "app/src/issues.py",
    "app/src/reporting.py",
    "src/bids_entity_rewriter.py",
]
# Import-time constants built from rules no project can change (the global entity order); each is commented where it is defined.
OFFICIAL_AT_IMPORT = {
    "src/bids_entity_rewriter.py": {"_ENTITY_ORDER", "_REQUIRED_ENTITIES"},
}


# Files whose own definitions need the import (the official defaults / import-time constants above).
MAY_IMPORT_LOADER = {
    "app/src/validator.py", "app/src/project_manager.py", "app/src/fixer.py", "src/bids_entity_rewriter.py",
}


def _offences(rel: str) -> list[str]:
    return scan_source((ROOT / rel).read_text(encoding="utf-8"), rel)


def scan_source(source: str, rel: str) -> list[str]:
    tree = ast.parse(source)
    definitions = set()  # nodes inside a module-level `NAME = ...` definition of a frozen default
    allowed = FROZEN | OFFICIAL_AT_IMPORT.get(rel, set())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in allowed for t in node.targets):
            definitions.update(ast.walk(node))
    found = []
    for node in ast.walk(tree):
        if node in definitions:
            continue
        if isinstance(node, ast.Name) and node.id in FROZEN:
            found.append(f"{rel}:{node.lineno} reads {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in FROZEN:  # validator.PRISM_MODALITIES
            found.append(f"{rel}:{node.lineno} reads .{node.attr}")
        elif isinstance(node, ast.ImportFrom):
            found += [f"{rel}:{node.lineno} imports {a.name}" for a in node.names if a.name in FROZEN]
            if rel not in MAY_IMPORT_LOADER:
                found += [f"{rel}:{node.lineno} imports load_entity_rules" for a in node.names if a.name == "load_entity_rules"]
        elif isinstance(node, ast.Call):
            func = node.func
            if getattr(func, "id", None) == "load_entity_rules" or getattr(func, "attr", None) == "load_entity_rules":
                found.append(f"{rel}:{node.lineno} calls load_entity_rules()")
    return found


def test_validation_code_does_not_read_frozen_modality_rules():
    offences = [line for rel in GUARDED for line in _offences(rel)]
    assert not offences, "read current_specification().rules instead:\n" + "\n".join(offences)


# --- the scanner itself: it must not be easy to get around -------------------------------------

import pytest


@pytest.mark.parametrize(
    "source",
    [
        "from validator import MODALITY_PATTERNS as MP\n",
        "import validator\nx = validator.BIDS_MODALITIES\n",
        "import src.entity_rules as er\nr = er.load_entity_rules()\n",
        "from src.entity_rules import load_entity_rules as ler\nr = ler()\n",
        "x = PRISM_MODALITIES\n",
        "r = load_entity_rules()\n",
    ],
    ids=["aliased import", "module attribute", "attribute call", "aliased loader", "plain name", "plain call"],
)
def test_the_scanner_catches_the_usual_ways_around_it(source):
    assert scan_source(source, "app/src/example.py")


def test_the_scanner_lets_definitions_and_the_specification_through():
    assert scan_source("from src.specification import current_specification\nr = current_specification().rules\n", "app/src/example.py") == []
    assert scan_source("PRISM_MODALITIES = load_entity_rules().project_modalities\n", "app/src/project_manager.py") == []
    assert scan_source("from src.entity_rules import load_entity_rules\n_X = load_entity_rules()\n", "app/src/fixer.py") != []  # _X is not allowed
