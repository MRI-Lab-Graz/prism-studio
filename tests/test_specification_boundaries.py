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
]


def _offences(rel: str) -> list[str]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    definitions = set()  # nodes inside a module-level `NAME = ...` definition of a frozen default
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in FROZEN for t in node.targets):
            definitions.update(ast.walk(node))
    found = []
    for node in ast.walk(tree):
        if node in definitions:
            continue
        if isinstance(node, ast.Name) and node.id in FROZEN:
            found.append(f"{rel}:{node.lineno} reads {node.id}")
        elif isinstance(node, ast.ImportFrom):
            found += [f"{rel}:{node.lineno} imports {a.name}" for a in node.names if a.name in FROZEN]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", None) == "load_entity_rules":
            found.append(f"{rel}:{node.lineno} calls load_entity_rules()")
    return found


def test_validation_code_does_not_read_frozen_modality_rules():
    offences = [line for rel in GUARDED for line in _offences(rel)]
    assert not offences, "read current_specification().rules instead:\n" + "\n".join(offences)
