"""Session-order prism_tools command handlers (thin adapters over src.session_order)."""

from __future__ import annotations

import json
import sys

from src.session_map import SessionMapError, project_session_labels
from src.session_order import (
    import_session_order,
    load_session_order,
    remove_order_entries,
    set_order_entries,
)


def _fail(exc: Exception) -> None:
    print(f"Error: {exc}")
    sys.exit(2)


def cmd_session_order_show(args) -> None:
    try:
        labels = project_session_labels(args.project)
        order = load_session_order(args.project)
    except SessionMapError as exc:
        _fail(exc)
    if getattr(args, "json", False):
        print(json.dumps({"session_labels": labels, "order": order}, indent=2, ensure_ascii=False))
        return
    print(f"Session labels: {labels}")
    for participant, entries in order.items():
        print(f"  {participant}: " + ", ".join(f"{n} -> {name}" for n, name in entries.items()))
    if not order:
        print("  (no entries; add them with `session-order set` or `session-order import`)")


def cmd_session_order_set(args) -> None:
    try:
        set_order_entries(args.project, args.participant, {args.number: args.session})
    except SessionMapError as exc:
        _fail(exc)
    print(f"{args.participant}: session {args.number} is {args.session}")


def cmd_session_order_unset(args) -> None:
    try:
        remove_order_entries(
            args.project, args.participant, [args.number] if args.number else None
        )
    except SessionMapError as exc:
        _fail(exc)
    print(f"Removed {args.participant}" + (f" session {args.number}" if args.number else "") + " from the session order")


def cmd_session_order_import(args) -> None:
    try:
        order = import_session_order(args.project, args.file, replace=bool(args.replace))
    except SessionMapError as exc:
        _fail(exc)
    print(f"Session order now has {len(order)} participant(s)")
