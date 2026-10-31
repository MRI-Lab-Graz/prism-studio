"""Project prism_tools command handlers (thin adapters over src.project_documents)."""

from __future__ import annotations

import sys

from src.project_documents import generate_readme, regenerate_citation
from src.project_root import resolve_project_root_path


def _project_root(args):
    root = resolve_project_root_path(str(args.project))
    if root is None:
        print(f"Error: project not found: {args.project}")
        sys.exit(1)
    return root


def cmd_project_generate_readme(args) -> None:
    try:
        result = generate_readme(_project_root(args))
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(result["message"])
    print(result["path"])


def cmd_project_regenerate_citation(args) -> None:
    result = regenerate_citation(_project_root(args))
    print(result["message"])
    for issue in result.get("issues", []) + result.get("consistency_issues", []):
        print(f"Warning: {issue}")
