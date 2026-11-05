"""What the DataLad page shows next. Decided here; the CLI prints it, Studio and its JavaScript only render it."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src.datalad_execution import is_datalad_dataset
from src.share_publish import _git, has_sibling, validate_for_publish

SERVER = "origin"
REACHABLE_TIMEOUT_SECONDS = 10


def _reachable(root: Path) -> bool:
    """Can `origin` be asked? Never raises: a server that is down is a plain answer, not an error."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": os.environ.get("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")}
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-remote", "--exit-code", SERVER],
            capture_output=True, text=True, check=False, timeout=REACHABLE_TIMEOUT_SECONDS, env=env,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return out.returncode == 0


def datalad_state(project_root, *, check_server: bool = False, validate: bool = False) -> dict:
    """The project's DataLad state and the one `next_step` the page offers.

    next_step: install_datalad | enable | put_on_server | save | sync.
    ponytail: "up_to_date" is not produced; telling it apart from "sync" needs a fetch. Add when the page wants it.
    """
    from src.project_manager import ProjectManager

    root = Path(project_root)
    available = bool(shutil.which("datalad"))
    enabled = is_datalad_dataset(root)
    state: dict = {"enabled": enabled, "available": available, "unsaved_count": 0, "server": None, "other_servers": []}

    if enabled and available:
        state["unsaved_count"] = int(ProjectManager().check_datalad_clean_status(root).get("dirty_count") or 0)
        remotes = _git(root, "remote").split()
        state["other_servers"] = [r for r in remotes if r != SERVER]
        if has_sibling(root, SERVER):
            state["server"] = {
                "name": SERVER,
                "url": _git(root, "remote", "get-url", SERVER),
                "reachable": _reachable(root) if check_server else None,
            }
        if validate:
            errors = validate_for_publish(root)
            state["valid"] = not errors
            state["error_count"] = len(errors)

    if not available:
        state["next_step"] = "install_datalad"
    elif not enabled:
        state["next_step"] = "enable"
    elif state["server"] is None:
        state["next_step"] = "put_on_server"
    elif state["unsaved_count"]:
        state["next_step"] = "save"
    else:
        state["next_step"] = "sync"
    return state
