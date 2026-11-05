"""Open from server: get your own copy of a project from the lab server (`prism_tools datalad open-from-server`)."""

from __future__ import annotations

from pathlib import Path

from src.datalad_doctor import datalad_preflight, missing_identity_message
from src.datalad_execution import run_datalad_clone
from src.share_publish import location_problem


def open_from_server(location: str, target, *, line_callback=None) -> dict:
    """Clone the project at `location` into the empty or new folder `target`, with the server as `origin`.

    Nested sub-* datasets are installed without their data (Get data fetches it), and the save-gate hooks are
    installed in every dataset, because git does not clone hooks. Everything is refused before cloning: a bad
    location, a folder that is not empty, missing tools and a missing git name/email.
    reason: cloned | bad_location | target_not_empty | no_datalad | no_identity | clone_failed.
    """
    location = str(location or "").strip()
    target = Path(target).expanduser().absolute()

    def refuse(reason: str, message: str) -> dict:
        return {"success": False, "reason": reason, "path": str(target), "message": message}

    problem = location_problem(location)
    if problem:
        return refuse("bad_location", problem)
    if target.is_file() or target.is_dir() and any(target.iterdir()):
        return refuse("target_not_empty", f"{target} is not empty. Choose an empty or new folder for your copy.")
    # the folder that will hold the copy: the target itself when it exists (empty), else its parent
    problems = datalad_preflight(target if target.is_dir() else target.parent)
    tools = [p for p in problems if " is not installed." in p]
    if tools:
        return refuse("no_datalad", "\n".join(tools))
    identity = missing_identity_message()  # the same sentence the preflight reports
    if identity and identity in problems:
        return refuse("no_identity", identity)
    if problems:
        return refuse("clone_failed", "\n".join(problems))

    cloned = run_datalad_clone(location, target, line_callback=line_callback)
    if not cloned.get("success"):
        outcome = refuse("clone_failed", str(cloned.get("message") or "Could not open the project from the server."))
        outcome["clone"] = cloned
        return outcome

    from src.project_manager import ProjectManager

    outcome = {"success": True, "reason": "cloned", "path": str(target), "clone": cloned}
    ProjectManager()._install_save_gate_hooks(target, outcome)  # the same installer "Enable DataLad" uses
    hook = outcome["save_gate_hook"]
    message = f"Opened the project from the server in {target}. Use Get data to fetch the files you need."
    not_gated = [hook["skipped"]] if hook.get("skipped") else [
        *hook["errors"], *(f"{p} has another pre-commit hook" for p in hook["foreign"])
    ]
    if not_gated:  # the copy works, but an invalid commit would no longer be stopped: say so
        message += " Warning: the save gate is not installed everywhere: " + "; ".join(not_gated)
    outcome["message"] = message
    return outcome
