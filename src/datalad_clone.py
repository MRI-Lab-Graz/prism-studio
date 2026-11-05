"""Open from server: get your own copy of a project from the lab server (`prism_tools datalad open-from-server`)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.datalad_doctor import datalad_preflight, missing_identity_message, parse_ssh_target
from src.datalad_execution import run_datalad_clone, run_datalad_install_nested
from src.share_publish import location_problem

_TARGET_HELP = "Give the full path of an empty or new folder for your copy (for example /home/me/projects/study)."


def target_problem(target) -> str:
    """'' for a target folder given as a full path (CLI and Studio refuse the same way), else why it is refused."""
    raw = str(target or "").strip()
    return "" if raw and Path(raw).expanduser().is_absolute() else _TARGET_HELP


def _inside(value: str) -> bool:
    """A relative path that stays inside its dataset: what DataLad writes for a subdataset (`./sub-01`)."""
    norm = value.replace("\\", "/")
    parts = norm.split("/")
    return (
        bool(norm)
        and not norm.startswith(("/", "-"))
        and ":" not in norm  # drive letters, schemes, user@host:path and `::` transport helpers
        and ".." not in parts
        and any(part not in ("", ".") for part in parts)
        and not any(c.isspace() or ord(c) < 32 for c in norm)
    )


def nested_url_problem(url: str, location: str) -> str:
    """'' when a nested dataset's url (from the server's `.gitmodules`, untrusted) stays on the server, else why not.

    Accepted: a relative path inside the dataset, or an address under the exact `location` the user gave that also
    passes `location_problem`. Anything else could clone another repository of this computer or run ssh with options.
    """
    url = str(url or "")
    prefix = str(location or "").rstrip("/\\") + "/"
    if _inside(url):
        return ""
    if url.startswith(prefix) and _inside(url[len(prefix):]) and not location_problem(url):
        return ""
    return f"'{url}' is not inside the project on the server"


def _nested_datasets(root: Path, location: str) -> tuple[list[str], str]:
    """(subdataset paths of `root`, '') once every url and path in its `.gitmodules` is checked, else ([], problem)."""
    if (root / ".datalad" / "config").is_file():
        candidates = subprocess.run(
            ["git", "config", "-f", str(root / ".datalad" / "config"), "--get-regexp", "subdataset-source-candidate"],
            capture_output=True, text=True,
        )
        if candidates.stdout.strip():  # the server could point DataLad at any other address this way
            return [], f"{root} sets its own places to install nested datasets from; this is refused"
    if not (root / ".gitmodules").is_file():
        return [], ""
    listed = subprocess.run(
        ["git", "config", "-z", "-f", str(root / ".gitmodules"), "--get-regexp", r"^submodule\..*\.(path|url|datalad-url)$"],
        capture_output=True, text=True,
    )
    if listed.returncode not in (0, 1):  # 1: no entries
        return [], f"{root / '.gitmodules'} cannot be read: {listed.stderr.strip()}"
    modules: dict[str, dict[str, str]] = {}
    for entry in filter(None, listed.stdout.split("\0")):
        key, _, value = entry.partition("\n")
        name, _, field = key[len("submodule."):].rpartition(".")
        modules.setdefault(name, {})[field] = value
    paths = []
    for name, fields in modules.items():
        path = fields.get("path", "")
        if not _inside(path):
            return [], f"the nested dataset '{name}' has the path '{path}', which is not inside {root}"
        for url in [fields.get("url", ""), *([fields["datalad-url"]] if "datalad-url" in fields else [])]:
            problem = nested_url_problem(url, location)
            if problem:
                return [], f"the nested dataset '{path}' in {root}: {problem}"
        paths.append(path)
    return paths, ""


def _gate(dataset: Path, hooks: dict) -> None:
    """The save-gate hook for one dataset, with the installer "Enable DataLad" uses for each dataset."""
    from src.project_manager import ProjectManager

    outcome = ProjectManager()._install_save_gate_hook_for_nested(dataset)
    for key in ("installed", "foreign", "errors"):
        hooks[key].extend(outcome[key])
    if outcome.get("skipped"):
        hooks["skipped"] = outcome["skipped"]


def open_from_server(location: str, target, *, line_callback=None) -> dict:
    """Clone the project at `location` into the empty or new folder `target`, with the server as `origin`.

    Nested sub-* datasets are installed level by level without their data (Get data fetches it), each only after
    every url in its parent's `.gitmodules` is checked. The save-gate hook goes into each dataset as soon as it is
    there, because git does not clone hooks. Refused before cloning: a bad location or target, a folder that is not
    empty or is inside a git repository, missing tools and a missing git name/email.
    reason: cloned | bad_location | bad_target | target_not_empty | no_datalad | no_identity | clone_failed.
    """
    location = str(location or "").strip()

    def refuse(reason: str, message: str) -> dict:
        return {"success": False, "reason": reason, "path": str(target), "message": message}

    problem = location_problem(location)
    if problem:
        return refuse("bad_location", problem)
    if parse_ssh_target(location) is None:  # a folder: relative to where the user is, not to the target
        location = str(Path(location).expanduser().absolute())
    if target_problem(target):
        return refuse("bad_target", target_problem(target))
    target = Path(str(target).strip()).expanduser()
    if target.is_file() or target.is_dir() and any(target.iterdir()):
        return refuse("target_not_empty", f"{target} is not empty. Choose an empty or new folder for your copy.")
    # the folder that will hold the copy: the target itself when it exists (empty), else its parent
    holder = target if target.is_dir() else target.parent
    problems = datalad_preflight(holder)
    tools = [p for p in problems if " is not installed." in p]
    if tools:
        return refuse("no_datalad", "\n".join(tools))
    identity = missing_identity_message()  # the same sentence the preflight reports
    if identity and identity in problems:
        return refuse("no_identity", identity)
    inside = subprocess.run(["git", "-C", str(holder), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.stdout.strip() == "true":
        return refuse("bad_target", f"{target} is inside a git repository. Choose a folder outside it for your copy.")
    if problems:
        return refuse("clone_failed", "\n".join(problems))

    cloned = run_datalad_clone(location, target, line_callback=line_callback)
    if not cloned.get("success"):
        outcome = refuse("clone_failed", str(cloned.get("message") or "Could not open the project from the server."))
        outcome["clone"] = cloned
        return outcome

    hooks: dict = {"installed": [], "foreign": [], "errors": []}
    outcome = {"success": True, "reason": "cloned", "path": str(target), "clone": cloned, "save_gate_hook": hooks}
    _gate(target, hooks)

    def incomplete(detail: str) -> dict:  # no deletion: the user removes the folder and tries again
        outcome.update(success=False, reason="clone_failed", message=(
            f"The copy in {target} is incomplete: {detail}. Nothing more was installed. "
            f"Delete the folder {target} before trying again."
        ))
        return outcome

    pending = [target]
    while pending:
        root = pending.pop(0)
        paths, problem = _nested_datasets(root, location)
        if problem:
            return incomplete(problem)
        if not paths:
            continue
        got = run_datalad_install_nested(root, paths, line_callback=line_callback)
        if not got.get("success"):
            return incomplete(str(got.get("message") or "the nested datasets could not be installed"))
        for path in paths:
            _gate(root / path, hooks)
            pending.append(root / path)

    message = f"Opened the project from the server in {target}. Use Get data to fetch the files you need."
    not_gated = [hooks["skipped"]] if hooks.get("skipped") else [
        *hooks["errors"], *(f"{p} has another pre-commit hook" for p in hooks["foreign"])
    ]
    if not_gated:  # the copy works, but an invalid commit would no longer be stopped: say so
        message += " Warning: the save gate is not installed everywhere: " + "; ".join(not_gated)
    outcome["message"] = message
    return outcome
