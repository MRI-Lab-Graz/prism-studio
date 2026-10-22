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
    "src/bids_entity_rewriter.py",
]
# Import-time constants built from rules no project can change (the official eyetracking suffixes, the global
# entity order); each is commented where it is defined.
OFFICIAL_AT_IMPORT = {
    "app/src/fixer.py": {"_EYETRACKING_NAME_HINTS"},
    "src/bids_entity_rewriter.py": {"_ENTITY_ORDER", "_REQUIRED_ENTITIES"},
}


def _offences(rel: str) -> list[str]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
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
        elif isinstance(node, ast.ImportFrom):
            found += [f"{rel}:{node.lineno} imports {a.name}" for a in node.names if a.name in FROZEN]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", None) == "load_entity_rules":
            found.append(f"{rel}:{node.lineno} calls load_entity_rules()")
    return found


def test_validation_code_does_not_read_frozen_modality_rules():
    offences = [line for rel in GUARDED for line in _offences(rel)]
    assert not offences, "read current_specification().rules instead:\n" + "\n".join(offences)
