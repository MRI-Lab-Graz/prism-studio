"""rsync prism_tools command handlers (thin adapters over src.project_settings and ProjectManager)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.project_settings import rsync_sync_options, save_rsync_config


def cmd_rsync_config(args) -> None:
    """Save the project's remote target, label and exclude patterns: what Studio's "Save" on the remote panel does."""
    saved = save_rsync_config(Path(args.project).resolve(), args.remote_target, args.remote_label, args.exclude)
    print(f"Saved to {saved['config_path']}")


def cmd_rsync_sync(args) -> None:
    """Copy the project to its remote target with rsync: what Studio's "Sync now" does (the same ProjectManager call)."""
    from src.project_manager import ProjectManager

    as_json = getattr(args, "json", False)

    def progress(percent: int, message: str) -> None:
        print(f"[{percent:3d}%] {message}")

    result = ProjectManager().sync_project_to_remote(
        Path(args.project).resolve(),
        progress_callback=None if as_json else progress,
        **rsync_sync_options(args.remote_target, args.remote_label, args.exclude, args.verify),
    )
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(result.get("message", ""))
    if not result.get("success"):
        sys.exit(1)
