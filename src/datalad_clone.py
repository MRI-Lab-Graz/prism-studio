"""Open from server: get your own copy of a project from the lab server (`prism_tools datalad open-from-server`)."""

from __future__ import annotations

import os
import stat
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


# The only keys PRISM and DataLad write in these committed, server-controlled files. Anything else (url rewriting such
# as datalad.clone.url-substitute.* or url.*.insteadOf, source candidates, include.path, submodule update commands)
# could send a checked url elsewhere, so it is refused: an allowlist, never a list of bad keys.
_DATASET_CONFIG_KEYS = {"datalad.dataset.id"}
_SUBMODULE_FIELDS = {"path", "url", "datalad-id"}


def _entries(path: Path) -> tuple[list[tuple[str, str]], str]:
    """Every (key, value) in a git config file, includes NOT followed (an include is just a key here)."""
    listed = subprocess.run(
        ["git", "config", "--no-includes", "-z", "-f", str(path), "--list"], capture_output=True, text=True
    )
    if listed.returncode != 0:
        return [], f"{path} cannot be read: {listed.stderr.strip()}"
    return [tuple(entry.partition("\n")[::2]) for entry in filter(None, listed.stdout.split("\0"))], ""


def _not_real(path: Path, folder: bool = False) -> str:
    """'' when `path` is missing or a real file/folder; a symlink (also a dangling one) or anything else is refused.

    is_file() follows links, so a link to a file inside a not-yet-installed dataset would be skipped now and read
    by DataLad later.
    """
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return ""
    if stat.S_ISDIR(mode) if folder else stat.S_ISREG(mode):
        return ""
    return f"{path} is not a regular {'folder' if folder else 'file'} (a link or something else), which is not accepted"


def _gitlink_problem(root: Path, path: str) -> str:
    """'' when `path` is a nested dataset of `root` itself: one gitlink (mode 160000) at exactly that path in root's
    own index, and every folder on the way a real folder. Else a deeper path (`sub-01/ses-1`, which would be installed
    through sub-01's unchecked files) or a committed link (to `.`, or to another dataset of this computer) is refused.
    """
    listed = subprocess.run(
        ["git", "--literal-pathspecs", "-C", str(root), "ls-files", "-s", "-z", "--", path],
        capture_output=True, text=True,
    )
    entries = [entry for entry in listed.stdout.split("\0") if entry]
    gitlink = len(entries) == 1 and entries[0].startswith("160000 ") and entries[0].partition("\t")[2] == path
    parts = path.split("/")
    if gitlink and all(_real_folder(root.joinpath(*parts[:depth])) for depth in range(1, len(parts) + 1)):
        return ""
    return f"'{path}' is not a nested dataset of {root} (a link or a deeper path), which is not accepted"


def _real_folder(path: Path) -> bool:
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def _alternates_problem(folder: Path) -> str:
    """'' unless the server folder borrows objects from another repository (git clone would copy that and read it)."""
    for name in (".git/objects/info/alternates", "objects/info/alternates"):
        if os.path.lexists(folder / name):
            return f"{folder / name} lets the server folder read another repository, which is not accepted"
    return ""


def _origin_folder(root: Path) -> Path | None:
    """The local server folder `root` was cloned from (git wrote it, not the server), None for an ssh server."""
    url = subprocess.run(
        ["git", "-C", str(root), "config", "--get", "remote.origin.url"], capture_output=True, text=True
    ).stdout.strip()
    return Path(url) if url and parse_ssh_target(url) is None and Path(url).is_absolute() else None


def _nested_datasets(root: Path, location: str) -> tuple[list[str], list[str], str]:
    """(subdataset paths, urls, '') of `root` once its `.datalad/config` and `.gitmodules` are checked, else problem."""
    # git refuses some paths at checkout (a symlinked .gitmodules), DataLad still says install(ok): the files are gone
    try:
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        return [], [], f"git did not answer within 60 seconds for {root}, which is not accepted"
    if status.returncode != 0:  # e.g. git rejects `update = !command` in .gitmodules
        return [], [], f"git refuses {root}, which is not accepted ({status.stderr.strip()})"
    if status.stdout.strip():
        detail = "; ".join(status.stdout.strip().splitlines()[:3])
        return [], [], f"{root} was not checked out completely from the server ({detail})"
    config = root / ".datalad" / "config"
    for path, folder in ((root / ".datalad", True), (config, False), (root / ".gitmodules", False)):
        if _not_real(path, folder):
            return [], [], _not_real(path, folder)
    if config.is_file():
        entries, problem = _entries(config)
        if problem:
            return [], [], problem
        for key, _ in entries:
            if key not in _DATASET_CONFIG_KEYS:
                return [], [], f"{config} sets '{key}', which is not accepted (only datalad.dataset.id is)"
    if not (root / ".gitmodules").is_file():
        return [], [], ""
    entries, problem = _entries(root / ".gitmodules")
    if problem:
        return [], [], problem
    paths, urls = [], []
    for key, value in entries:
        section, _, rest = key.partition(".")
        name, _, field = rest.rpartition(".")
        if section != "submodule" or not name or field not in _SUBMODULE_FIELDS:
            return [], [], f"{root / '.gitmodules'} sets '{key}', which is not accepted"
        if field == "path":
            if not _inside(value):
                return [], [], f"the nested dataset '{name}' has the path '{value}', which is not inside {root}"
            if _gitlink_problem(root, value):
                return [], [], _gitlink_problem(root, value)
            paths.append(value)
        elif field == "url":
            if nested_url_problem(value, location):  # every url entry, also a repeated one
                return [], [], f"the nested dataset '{name}' in {root}: {nested_url_problem(value, location)}"
            urls.append(value)
    return paths, urls, ""


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
        if _alternates_problem(Path(location)):
            return refuse("bad_location", _alternates_problem(Path(location)))
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
        paths, urls, problem = _nested_datasets(root, location)
        if problem:
            return incomplete(problem)
        if not paths:
            continue
        origin = _origin_folder(root)  # DataLad clones <origin>/<path> or the url (relative to origin)
        for source in [*paths, *urls] if origin else ():
            problem = _alternates_problem(origin / source if _inside(source) else Path(source))
            if problem:
                return incomplete(problem)
        got = run_datalad_install_nested(root, paths, line_callback=line_callback)
        if not got.get("success"):
            return incomplete(str(got.get("message") or "the nested datasets could not be installed"))
        for path in paths:
            if _gitlink_problem(root, path):  # still a real folder now that it is installed
                return incomplete(_gitlink_problem(root, path))
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
