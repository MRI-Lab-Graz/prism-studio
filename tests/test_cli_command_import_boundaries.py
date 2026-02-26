#!/usr/bin/env python3
"""Import-boundary checks for CLI command modules.

Goal: keep `app/src/cli/commands/*` decoupled from each other and from CLI wiring.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "app" / "src" / "cli" / "commands"

FORBIDDEN_PREFIXES = (
    "src.cli.commands",
    "src.cli.dispatch",
    "src.cli.parser",
    "src.cli.entrypoint",
    "app.prism_tools",
    "prism_tools",
)


def _command_files() -> list[Path]:
    return sorted(
        p for p in COMMANDS_DIR.glob("*.py") if p.name != "__init__.py"
    )


def _import_targets(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    if isinstance(node, ast.ImportFrom):
        base = node.module or ""
        if base:
            return [base]
        # Relative import with no module target, e.g. `from . import x`
        return ["."]

    return []


def test_cli_command_modules_have_no_relative_imports() -> None:
    violations: list[str] = []

    for file_path in _command_files():
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                violations.append(
                    f"{file_path.relative_to(REPO_ROOT)}:{node.lineno} uses relative import"
                )

    assert not violations, "\n".join(violations)


def test_cli_command_modules_respect_import_boundaries() -> None:
    violations: list[str] = []

    for file_path in _command_files():
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            for target in _import_targets(node):
                normalized = target.lstrip(".")
                for forbidden in FORBIDDEN_PREFIXES:
                    if normalized == forbidden or normalized.startswith(forbidden + "."):
                        violations.append(
                            f"{file_path.relative_to(REPO_ROOT)}:{node.lineno} imports forbidden module '{target}'"
                        )

    assert not violations, "\n".join(violations)
