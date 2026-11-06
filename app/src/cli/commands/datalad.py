"""datalad doctor / keygen prism_tools command handlers (thin adapters over src.datalad_doctor)."""

from __future__ import annotations

import json
import sys

from src.datalad_doctor import get_git_identity, run_doctor, set_git_identity


def cmd_datalad_doctor(args) -> None:
    results = run_doctor(getattr(args, "url", None))
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


def cmd_datalad_sync(args) -> None:
    """Get the latest from the server, then publish: only a saved, valid dataset is sent (Studio's "Sync now")."""
    from src.share_publish import parse_identity, sync_with_server

    try:
        identity = parse_identity(args.as_identity) if getattr(args, "as_identity", None) else None
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    result = sync_with_server(
        args.project,
        sibling_name=args.sibling_name,
        identity=identity,
        line_callback=None if args.json else print,
        allow_invalid=bool(getattr(args, "allow_invalid", False)),
    )
    _print_push_result(args, result)


def cmd_datalad_put_on_server(args) -> None:
    """Create the project's dataset on the lab server, then send it if it validates (Studio's "Put on server")."""
    from src.share_publish import parse_identity, put_on_server

    try:
        identity = parse_identity(args.as_identity) if getattr(args, "as_identity", None) else None
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    result = put_on_server(
        args.project,
        args.location,
        sibling_name=args.sibling_name,
        identity=identity,
        line_callback=None if args.json else print,
        allow_invalid=bool(getattr(args, "allow_invalid", False)),
    )
    _print_push_result(args, result)


def cmd_datalad_open_from_server(args) -> None:
    """Get your own copy of a project from the lab server into an empty or new folder (Studio's "Open from server")."""
    from src.datalad_clone import open_from_server, target_problem

    problem = target_problem(args.target)  # the check Studio's route makes before it starts a job
    if problem:
        _print_result(args, {"success": False, "reason": "bad_target", "path": str(args.target), "message": problem})
    result = open_from_server(args.location, args.target, line_callback=None if args.json else print)
    _print_result(args, result)


def cmd_datalad_get_data(args) -> None:
    """Fetch the data of your copy from the server, with the export's filters (Studio's "Get data")."""
    from src.datalad_get_data import filters_from_options, get_data
    from src.cli.services.export_args import export_data_from_args

    result = get_data(
        args.project,
        sibling_name=getattr(args, "sibling_name", None),
        line_callback=None if args.json else print,
        **filters_from_options(export_data_from_args(args)),
    )
    _print_result(args, result)


def _print_push_result(args, result: dict) -> None:
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(result.get("message", ""))
        for line in result.get("errors", [])[:20]:
            print(f"  - {line}")
    if not result["success"]:
        sys.exit(1)


def _print_result(args, result: dict) -> None:
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(result.get("message") or result.get("error") or "")
    if not result.get("success"):
        sys.exit(1)


def cmd_datalad_enable(args) -> None:
    """Make the project a DataLad dataset and save a first snapshot (Studio's "Enable DataLad")."""
    from src.project_manager import DEFAULT_ENABLE_DATALAD_MESSAGE, ENABLE_DATALAD_NEEDS_CONFIRMATION

    if not args.yes:
        print(ENABLE_DATALAD_NEEDS_CONFIRMATION)
        sys.exit(2)

    message = str(args.message or "").strip() or DEFAULT_ENABLE_DATALAD_MESSAGE
    manager = _manager()
    result = manager.enable_datalad_for_project(args.project, message=message)
    while result.get("enable_continue"):  # nested datasets are registered in batches, as Studio does
        result = manager.enable_datalad_for_project(args.project, message=message)
    _print_result(args, result)


def cmd_datalad_save(args) -> None:
    """Save the project's changes as a DataLad snapshot (Studio's "Save")."""
    from src.project_manager import DEFAULT_SNAPSHOT_MESSAGE

    message = str(args.message or "").strip() or DEFAULT_SNAPSHOT_MESSAGE
    allow_invalid = bool(getattr(args, "allow_invalid", False))
    _print_result(args, _manager().save_datalad_snapshot(args.project, message=message, allow_invalid=allow_invalid))


def cmd_datalad_status(args) -> None:
    """Show the project's DataLad state and the next step (Studio's DataLad page and navbar count).

    Studio's /api/projects/datalad/state runs the same function."""
    from src.datalad_state import datalad_state

    state = datalad_state(
        args.project,
        check_server=bool(getattr(args, "check_server", False)),
        validate=bool(getattr(args, "validate", False)),
        check_nested=bool(getattr(args, "check_nested", False)),
    )
    if getattr(args, "json", False):
        print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
        return
    print(state["message"])
    print(f"Next step: {state['next_step']}")
    if state.get("nested_unregistered"):
        print(f"{state['nested_unregistered']} subject dataset(s) not registered yet: run `datalad enable` to finish.")
    server = state["server"]
    if server:
        reach = {True: "reachable", False: "not reachable", None: "not checked"}[server["reachable"]]
        print(f"Server {server['name']}: {server['url']} ({reach})")
    for name in state["other_servers"]:
        print(f"Server found as '{name}'. Use --sibling-name {name}.")
    if "valid" in state:
        print("Valid." if state["valid"] else f"{state['error_count']} validation error(s).")


def cmd_datalad_update(args) -> None:
    """Get the latest saved changes from the server (Studio's "Get latest", and what it runs when a project opens)."""
    _print_result(args, _manager().update_datalad_from_server(args.project, sibling_name=args.sibling_name))


def cmd_datalad_identity(args) -> None:
    """Show or set the name and email git signs your saved changes with (this computer's, for all projects).

    Studio's Settings page runs the same functions."""
    try:
        identity = set_git_identity(args.name, args.email) if (args.name or args.email) else get_git_identity()
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    identity = {"name": identity["name"], "email": identity["email"]}
    if getattr(args, "json", False):
        print(json.dumps({"success": True, **identity}, ensure_ascii=False))
    else:
        print(f"{identity['name'] or '(no name)'} <{identity['email'] or 'no email'}>")
