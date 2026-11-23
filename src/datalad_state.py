"""What the DataLad page shows next. Decided here; the CLI prints it, Studio and its JavaScript only render it."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.datalad_execution import is_datalad_dataset
from src.share_publish import _git, has_sibling

SERVER = "origin"


def datalad_state(project_root, *, check_nested: bool = False) -> dict:
    """The project's DataLad state and the one `next_step` the page offers.

    next_step: install_datalad | enable | put_on_server | save | sync; with "enable", `enable_kind` says whether DataLad
    is off ("first") or on with subject datasets not registered yet ("finish", only known with `check_nested`).
    `checked` is False when the unsaved changes could not be counted; then "save" is advised, never "sync".
    `check_nested` runs `datalad subdatasets` (about a second), so the page asks for it and the navbar does not.
    """
    from src.project_manager import ProjectManager

    root = Path(project_root)
    available = bool(shutil.which("datalad"))
    enabled = is_datalad_dataset(root)
    state: dict = {"enabled": enabled, "available": available, "checked": False, "message": "", "unsaved_count": 0, "server": None}

    if enabled and available:
        clean = ProjectManager().check_datalad_clean_status(root)
        state["checked"] = bool(clean.get("checked"))
        state["message"] = str(clean.get("message") or "")
        state["unsaved_count"] = int(clean.get("dirty_count") or 0)
        if has_sibling(root, SERVER):
            state["server"] = {"name": SERVER, "url": _git(root, "remote", "get-url", SERVER)}
        if check_nested:
            missing = ProjectManager()._summarize_nested_subdatasets(root)["missing_subdatasets"]
            state["nested_unregistered"] = len(missing)
            state["nested_unregistered_paths"] = missing

    if not available:
        state["next_step"] = "install_datalad"
    elif not enabled or state.get("nested_unregistered"):
        state["next_step"] = "enable"
        state["enable_kind"] = "finish" if enabled else "first"
    elif state["server"] is None:
        state["next_step"] = "put_on_server"
    elif state["unsaved_count"] or not state["checked"]:
        state["next_step"] = "save"
    else:
        state["next_step"] = "sync"
    return state
