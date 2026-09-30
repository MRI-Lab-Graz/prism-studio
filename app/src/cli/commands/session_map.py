"""Session-map prism_tools command handlers (thin adapters over src.session_map)."""

from __future__ import annotations

import json
import sys

from src.session_map import (
    SessionMapError,
    load_session_map,
    project_timepoints,
    remove_session_entries,
    set_session_entries,
)


def cmd_session_map_show(args) -> None:
    try:
        timepoints = project_timepoints(args.project)
        mapping = load_session_map(args.project)
    except SessionMapError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {"timepoints": timepoints, "map": mapping}, indent=2, ensure_ascii=False
            )
        )
        return
    print(f"Timepoints: {timepoints or '(no project.json)'}")
    for label, target in mapping.items():
        print(f"  {label!r} -> {target}")
    if not mapping:
        print("  (no entries; add them with `session-map set`)")


def cmd_session_map_set(args) -> None:
    try:
        set_session_entries(args.project, {args.label: args.target})
    except SessionMapError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    print(f"Mapped {args.label!r} -> {args.target}")


def cmd_session_map_unset(args) -> None:
    try:
        remove_session_entries(args.project, [args.label])
    except SessionMapError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    print(f"Removed {args.label!r} from the session map")
