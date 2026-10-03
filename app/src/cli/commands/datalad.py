"""datalad doctor / keygen prism_tools command handlers (thin adapters over src.datalad_doctor)."""

from __future__ import annotations

import json
import sys

from src.datalad_doctor import run_doctor


def _server_url(args):
    if getattr(args, "url", None):
        return args.url
    project = getattr(args, "project", None)
    if project:
        from src.config import load_config

        return load_config(str(project)).datalad_ria_store_url
    return None


def cmd_datalad_doctor(args) -> None:
    results = run_doctor(_server_url(args))
    if getattr(args, "json", False):
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"[{'ok' if r['ok'] else 'FAIL'}] {r['name']}: {r['detail']}")
            if not r["ok"] and r["fix"]:
                print(f"       -> {r['fix']}")
    if not all(r["ok"] for r in results):
        sys.exit(1)



def _manager():
    from src.project_manager import ProjectManager

    return ProjectManager()


def _run_push_operation(args, operation: str, **extra) -> None:
    """Shared by sync/finalize: run the ProjectManager operation, print, set the exit code."""
    as_json = getattr(args, "json", False)

    def progress(percent: int, message: str) -> None:
        print(f"[{percent:3d}%] {message}")

    try:
        result = getattr(_manager(), operation)(
            args.project,
            ria_url=args.url,
            sibling_name=args.sibling_name,
            alias=args.alias,
            progress_callback=None if as_json else progress,
            **extra,
        )
    except ValueError as exc:  # e.g. no server URL configured
        print(f"Error: {exc}")
        sys.exit(2)
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(result.get("message", ""))
    if not result.get("success"):
        sys.exit(1)


def cmd_datalad_sync(args) -> None:
    _run_push_operation(args, "sync_project_to_ria", verify=args.verify)


def cmd_datalad_finalize(args) -> None:
    if not args.yes:
        print(
            "Finalize pushes once more, verifies, then removes this computer's connection to "
            "the server (local files are kept). Re-run with --yes to do it."
        )
        sys.exit(2)
    _run_push_operation(
        args,
        "finalize_project_upload",
        verify_mode=args.verify_mode,
        mark_annex_dead=args.mark_annex_dead,
    )
