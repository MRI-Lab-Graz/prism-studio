"""The CLI must reach business logic through `src.*` backend modules, never
through the Flask layer (`src.web.*`). Studio routes call the CLI commands /
backend, not the other way round -- see
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md and CLAUDE.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "cli"


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def test_cli_does_not_import_flask_layer():
    offenders = [
        f"{path.relative_to(CLI_ROOT.parents[2])}: {module}"
        for path in sorted(CLI_ROOT.rglob("*.py"))
        for module in _imported_modules(path)
        if module == "src.web" or module.startswith("src.web.") or module == "flask"
    ]
    assert offenders == [], "CLI imports the Flask layer:\n" + "\n".join(offenders)
