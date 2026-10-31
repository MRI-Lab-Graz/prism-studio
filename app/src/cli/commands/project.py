"""Project prism_tools command handlers (thin adapters over src.project_documents)."""

from __future__ import annotations

import json
import sys

from src.project_delete import ProjectDeleteRefused, delete_project
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


def cmd_project_fixable(args) -> None:
    """List what `project fix` can repair (the list Studio's Fix button shows; the same ProjectManager method runs both)."""
    from src.project_manager import ProjectManager

    issues = ProjectManager().get_fixable_issues(str(_project_root(args)))
    if args.json:
        print(json.dumps(issues, indent=2, ensure_ascii=False))
    else:
        for issue in issues:
            print(f"{issue.get('issue_code', '')}: {issue.get('description') or issue.get('error', '')}")
        if not issues:
            print("Nothing to fix.")
    if any("error" in issue for issue in issues):
        sys.exit(1)


def cmd_project_fix(args) -> None:
    """Repair the fixable issues (all, or the --codes given): what Studio's Fix button does."""
    from src.project_manager import ProjectManager

    codes = [c.strip() for c in args.codes.split(",") if c.strip()] if args.codes else None
    result = ProjectManager().apply_fixes(str(_project_root(args)), codes)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result["success"]:
        for fix in result["applied_fixes"]:
            print(f"Fixed {fix.get('issue_code', '')}: {fix.get('description', '')}")
        print(f"{result['count']} fix(es) applied.")
    else:
        print(f"Error: {result['error']}")
    if not result["success"]:
        sys.exit(1)


def cmd_project_delete(args) -> None:
    """Delete a project folder from disk (what Studio's Delete button does; the same function runs both).
    --confirm-name must echo the project's exact name."""
    try:
        root = delete_project(str(args.project), str(args.confirm_name or "").strip())
    except ProjectDeleteRefused as refused:
        print(f"Error: {refused}")
        sys.exit(1)
    print(f"Deleted {root}")
