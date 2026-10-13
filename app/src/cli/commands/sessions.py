"""`sessions` prism_tools commands: review how repeated responses map to sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.participants_converter import load_participant_source
from src.participants_sessions import session_assignment_table
from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    unset_assignment,
)


def cmd_sessions_review(args) -> None:
    try:
        df, _ = load_participant_source(Path(args.input).expanduser().resolve())
        decisions = load_session_assignments(args.project) if args.project else {}
        rows, warnings = session_assignment_table(
            df, args.id_column, args.date_column, decisions=decisions
        )
    except ValueError as exc:  # SessionAssignmentError is a ValueError
        print(f"Error: {exc}")
        sys.exit(2)
    if getattr(args, "json", False):
        print(json.dumps({"rows": rows, "warnings": warnings}, indent=2, ensure_ascii=False))
        return
    print(f"{'participant':<14}{'response':<10}{'date':<21}{'done':<6}{'lastpage':<9}session")
    for r in rows:
        shown = r["session"] if r["session"] is not None else f"left out ({r['reason']})"
        print(
            f"{r['participant']:<14}{r['response_id']:<10}{r['date'][:19]:<21}"
            f"{'yes' if r['completed'] else 'no':<6}{r['lastpage']:<9}{shown}"
        )
    for warning in warnings:
        print(f"WARNING: {warning}")


def cmd_sessions_set(args) -> None:
    try:
        set_assignment(
            args.project, args.response, skip=bool(args.skip), session=args.session
        )
    except SessionAssignmentError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    what = "skipped" if args.skip else f"session {args.session!r}"
    print(f"Response {args.response}: {what}")


def cmd_sessions_unset(args) -> None:
    try:
        unset_assignment(args.project, args.response)
    except SessionAssignmentError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    print(f"Response {args.response}: decision removed (automatic rule applies)")
