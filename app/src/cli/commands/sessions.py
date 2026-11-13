"""`sessions` prism_tools commands: review how repeated responses map to sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.participants_converter import load_participant_source
from src.participants_sessions import session_assignment_table
from src.session_order import content_session_order
from src.session_assignments import (
    load_session_assignments,
    set_assignment,
    survey_id_of,
    unset_assignment,
)


def _fail(exc: Exception) -> None:
    print(f"Error: {exc}")
    sys.exit(2)


def cmd_sessions_review(args) -> None:
    source = Path(args.input).expanduser().resolve()
    try:
        df, _ = load_participant_source(source)
        survey_id = survey_id_of(source)
        decisions = load_session_assignments(args.project, survey_id) if args.project else {}
        rows, warnings = session_assignment_table(
            df, args.id_column, args.date_column, decisions=decisions,
            imported_root=args.project if getattr(args, "skip_existing", False) else None,
            survey_id=survey_id,
            order=content_session_order(args.project) if args.project else None,
        )
    except (ValueError, OSError) as exc:  # SessionAssignmentError is a ValueError
        _fail(exc)
    if getattr(args, "json", False):
        print(json.dumps({"survey_id": survey_id, "rows": rows, "warnings": warnings}, indent=2, ensure_ascii=False))
        return
    print(f"Survey: {survey_id}")
    table = [
        (
            r["participant"],
            r["response_id"],
            r["date"][:19],
            "yes" if r["completed"] else "no",
            r["lastpage"],
            r["session"] if r["session"] is not None else f"left out ({r['reason']})",
        )
        for r in rows
    ]
    table.insert(0, ("participant", "response", "date", "done", "lastpage", "session"))
    widths = [max(len(str(row[i])) for row in table) + 2 for i in range(5)]
    for row in table:
        print("".join(f"{str(cell):<{w}}" for cell, w in zip(row, widths)) + str(row[5]))
    for warning in warnings:
        print(f"WARNING: {warning}")


def cmd_sessions_set(args) -> None:
    try:
        set_assignment(
            args.project, args.response, survey_id=args.survey,
            skip=bool(args.skip), session=args.session, include=bool(args.include),
        )
    except (ValueError, OSError) as exc:
        _fail(exc)
    what = "skipped" if args.skip else "included" if args.include else f"session {args.session!r}"
    print(f"Response {args.response} (survey {args.survey}): {what}")


def cmd_sessions_unset(args) -> None:
    try:
        unset_assignment(args.project, args.response, survey_id=args.survey)
    except (ValueError, OSError) as exc:
        _fail(exc)
    print(f"Response {args.response} (survey {args.survey}): decision removed (automatic rule applies)")


def cmd_sessions_forget_import(args) -> None:
    from src.survey_existing import forget_imports

    if not (args.subject or args.response):
        _fail(ValueError("Name what to forget: --subject (with optional --session) and/or --response"))
    root = Path(args.project).expanduser()
    root = root.parent if root.is_file() else root
    forgotten = forget_imports(
        root, subject=args.subject, session=args.session, survey_id=args.survey, responses=args.response
    )
    for sub, ses in forgotten["slots"]:
        print(f"Forgot {sub}/{ses}" + (f"; delete its folder by hand: {sub}/{ses}" if any(root.glob(f"**/{sub}/{ses}")) else ""))
    for response_id in forgotten["seen"]:
        print(f"Forgot reviewed response {response_id} (survey {args.survey})")
    if not (forgotten["slots"] or forgotten["seen"]):
        print("Nothing in the ledger matched.")
