#!/usr/bin/env python3
"""THE RULE (CLAUDE.md): the CLI executes, Studio only triggers.

Lists every backend function Studio imports that no CLI command imports: the places where Studio does
something the command line cannot. ``scripts/cli_studio_baseline.json`` holds the ones reviewed so far; the
list may only shrink. Run ``python scripts/check_cli_studio_parity.py`` to see what is new, ``--update-baseline``
only to REMOVE entries that are fixed.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).with_name("cli_studio_baseline.json")


def _package(repo: Path, file: Path) -> list[str]:
    """Dotted package of a file as Python imports it: app/src/web/x.py -> ['src', 'web']."""
    rel = file.relative_to(repo)
    parts = list(rel.parent.parts)
    return parts[1:] if parts and parts[0] == "app" else parts


def _is_app_src_module(repo: Path, module: str) -> bool:
    path = repo / "app" / "src" / Path(*module.split("."))
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def _imports(repo: Path, files) -> set[str]:
    found = set()
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        package = _package(repo, file)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            base = package[: len(package) - (node.level - 1)] if node.level else []
            module = ".".join(base + ([node.module] if node.module else []))
            if not module.startswith("src.") and _is_app_src_module(repo, module):
                module = "src." + module  # `core.validation` and `src.core.validation` are the same file
            for alias in node.names:
                found.add(f"{module}:{alias.name}")
    return found


def _is_backend_function(entry: str) -> bool:
    module, name = entry.split(":")
    if not module.startswith("src.") or module.startswith("src.web") or module.startswith("src.cli"):
        return False
    return not (name[:1].isupper())  # classes and CONSTANTS are not behaviour


def studio_only_backend_calls(repo) -> set[str]:
    repo = Path(repo)
    studio = list((repo / "app" / "src" / "web").rglob("*.py")) + [repo / "app" / "prism-studio.py"]
    cli = list((repo / "app" / "src" / "cli").rglob("*.py")) + [repo / "app" / "prism.py", repo / "prism_tools.py"]
    cli_calls = {c for c in _imports(repo, [f for f in cli if f.exists()])}
    return {e for e in _imports(repo, [f for f in studio if f.exists()]) if _is_backend_function(e) and e not in cli_calls}


def new_studio_only_calls(repo, baseline=DEFAULT_BASELINE) -> set[str]:
    known = set(json.loads(Path(baseline).read_text(encoding="utf-8"))) if Path(baseline).exists() else set()
    return studio_only_backend_calls(repo) - known


def main(argv: list[str]) -> int:
    repo = Path(__file__).resolve().parents[1]
    current = studio_only_backend_calls(repo)
    if "--update-baseline" in argv:  # only ever to drop entries that were fixed
        old = json.loads(DEFAULT_BASELINE.read_text(encoding="utf-8")) if DEFAULT_BASELINE.exists() else {}
        kept = {name: old.get(name, "to review") for name in sorted(current)}
        DEFAULT_BASELINE.write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"baseline: {len(kept)} entries ({len(set(old) - set(kept))} removed, {len(set(kept) - set(old))} added)")
        return 0
    new = new_studio_only_calls(repo)
    print(f"{len(current)} Studio-only backend calls in the baseline's scope; {len(new)} new")
    for name in sorted(new):
        print(f"  NEW  {name}")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
