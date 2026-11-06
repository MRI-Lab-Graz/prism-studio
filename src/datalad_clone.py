"""Open from server: get your own copy of a project from the lab server (`prism_tools datalad open-from-server`)."""

from __future__ import annotations

import os
import posixpath
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


def nested_url_problem(url: str, path: str) -> str:
    """'' when a nested dataset's url (from the server's `.gitmodules`, untrusted) is `./<path>` of that very dataset.

    That is what DataLad and PRISM write (`./sub-01`, `./derivatives`). Anything else, also another relative path or an
    address on the server, could make DataLad clone another repository of this computer or run ssh with options.
    """
    url = str(url or "")
    if url.startswith("./") and _inside(url) and not url.endswith("/") and posixpath.normpath(url) == posixpath.normpath(path):
        return ""
    return f"'{url}' is not inside the project on the server, which is not accepted (only './{path}' is)"


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


def _server_folder_problem(base: Path, source: str = "") -> str:
    """'' when the folder server's `base`, every folder down to `base/source` and its `.git` are real folders.

    A folder server is read on this computer: a link (also one a push commits into the server's work tree) or a
    `gitdir:` file there could name any other repository of the user.
    """
    here, folders = base, [base]
    for part in [*(part for part in source.split("/") if part not in ("", ".")), ".git"]:
        here = here / part
        folders.append(here)
    for folder in folders:
        if not _real_folder(folder):
            return f"{folder} on the server is not a real folder (a link, a file or missing), which is not accepted"
    return ""


def _copy_alternates_problem(copy: Path) -> str:
    """'' unless git gave the copy an alternates file (it would read objects of another repository)."""
    alternates = copy / ".git" / "objects" / "info" / "alternates"
    if os.path.lexists(alternates):
        return f"{alternates} was copied from the server and names another repository, which is not accepted"
    return ""


def _alternates_problem(folder: Path) -> str:
    """'' unless the server folder borrows objects from another repository (git clone would copy that and read it)."""
    for name in (".git/objects/info/alternates", "objects/info/alternates"):
        if os.path.lexists(folder / name):
            return f"{folder / name} lets the server folder read another repository, which is not accepted"
    return ""


def _remote_folders(root: Path) -> list[Path]:
    """The local folders among `root`'s remotes (git wrote them, not the server): DataLad clones `<remote>/<path>`."""
    listed = subprocess.run(
        ["git", "-C", str(root), "config", "--get-regexp", r"^remote\..*\.url$"], capture_output=True, text=True
    ).stdout.splitlines()
    urls = [line.partition(" ")[2].strip() for line in listed]
    return [Path(url) for url in urls if url and parse_ssh_target(url) is None and Path(url).is_absolute()]


def _nested_datasets(root: Path, *, fresh: bool) -> tuple[list[str], str]:
    """(subdataset paths, '') of `root` once its `.datalad/config` and `.gitmodules` are checked, else ([], problem).

    `fresh`: `root` was just cloned, so anything git did not check out means it refused a path (a symlinked
    .gitmodules) while DataLad still said install(ok). Your own copy may have unsaved changes; they are yours.
    """
    try:
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        return [], f"git did not answer within 60 seconds for {root}, which is not accepted"
    if status.returncode != 0:  # e.g. git rejects `update = !command` in .gitmodules
        return [], f"git refuses {root}, which is not accepted ({status.stderr.strip()})"
    if fresh and status.stdout.strip():
        detail = "; ".join(status.stdout.strip().splitlines()[:3])
        return [], f"{root} was not checked out completely from the server ({detail})"
    config = root / ".datalad" / "config"
    for path, folder in ((root / ".datalad", True), (config, False), (root / ".gitmodules", False)):
        if bad := _not_real(path, folder):
            return [], bad
    if config.is_file():
        entries, problem = _entries(config)
        if problem:
            return [], problem
        for key, _ in entries:
            if key not in _DATASET_CONFIG_KEYS:
                return [], f"{config} sets '{key}', which is not accepted (only datalad.dataset.id is)"
    if not (root / ".gitmodules").is_file():
        return [], ""
    entries, problem = _entries(root / ".gitmodules")
    if problem:
        return [], problem
    fields: dict[str, dict[str, list[str]]] = {}
    for key, value in entries:
        section, _, rest = key.partition(".")
        name, _, field = rest.rpartition(".")
        if section != "submodule" or not name or field not in _SUBMODULE_FIELDS:
            return [], f"{root / '.gitmodules'} sets '{key}', which is not accepted"
        fields.setdefault(name, {}).setdefault(field, []).append(value)
    paths = []
    for name, entry in fields.items():
        if len(entry.get("path", [])) != 1 or not entry.get("url"):
            return [], f"the nested dataset '{name}' in {root} needs exactly one path and a url, which is not accepted"
        path = entry["path"][0]
        if not _inside(path):
            return [], f"the nested dataset '{name}' has the path '{path}', which is not inside {root}"
        if bad := _gitlink_problem(root, path):
            return [], bad
        for url in entry["url"]:  # every url entry, also a repeated one
            if bad := nested_url_problem(url, path):
                return [], f"the nested dataset '{name}' in {root}: {bad}"
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


def _installed(dataset: Path) -> bool:
    return os.path.lexists(dataset / ".git")


def install_nested_checked(top: Path, hooks: dict, *, fresh: bool, wanted=None, line_callback=None) -> str:
    """Install the not yet installed nested datasets under `top` level by level, without data; '' or the problem.

    The one installer for nested datasets named by a server (open from server, Get data): each dataset's
    `.datalad/config` and `.gitmodules` are checked before anything below it is installed, a folder server is read
    only through real folders, nothing borrows another repository's objects, and every new dataset gets the save-gate
    hook. `wanted(path relative to top)` limits what is installed; installed datasets are always looked into.
    On a problem nothing more is installed.
    """
    pending = [top]
    while pending:
        root = pending.pop(0)
        paths, problem = _nested_datasets(root, fresh=fresh)
        if problem:
            return problem
        new = []
        for path in paths:
            if _installed(root / path):
                pending.append(root / path)
            elif wanted is None or wanted((root / path).relative_to(top).as_posix()):
                new.append(path)
        if not new:
            continue
        for base in _remote_folders(root):  # DataLad clones <remote>/<path> (the url is ./<path>, the same)
            for path in new:
                problem = _server_folder_problem(base, path) or _alternates_problem(base / path)
                if problem:
                    return f"the nested dataset source '{path}' of {root}: {problem}"
        got = run_datalad_install_nested(root, new, line_callback=line_callback)
        if not got.get("success"):
            return str(got.get("message") or "the nested datasets could not be installed")
        for path in new:
            if bad := _copy_alternates_problem(root / path) or _gitlink_problem(root, path):  # still a real folder when installed
                return bad
            _gate(root / path, hooks)
            pending.append(root / path)
    return ""


def gate_warning(hooks: dict) -> str:
    """'' or a sentence naming the datasets without the save gate (an invalid commit is not stopped there)."""
    not_gated = [hooks["skipped"]] if hooks.get("skipped") else [
        *hooks["errors"], *(f"{p} has another pre-commit hook" for p in hooks["foreign"])
    ]
    return " Warning: the save gate is not installed everywhere: " + "; ".join(not_gated) if not_gated else ""


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
    # the folder that will hold the copy: the target itself when it exists (empty), else its nearest existing parent
    holder = target
    while not holder.is_dir():  # DataLad creates missing parents itself
        holder = holder.parent
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
    if parse_ssh_target(location) is None:  # read on this computer: real folders only, no borrowed objects
        problem = _server_folder_problem(Path(location)) or _alternates_problem(Path(location))
        if problem:
            return refuse("bad_location", problem)

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

    problem = _copy_alternates_problem(target) or install_nested_checked(
        target, hooks, fresh=True, line_callback=line_callback
    )
    if problem:
        return incomplete(problem)
    # the copy works without the gate, but an invalid commit would no longer be stopped: say so
    opened = f"Opened the project from the server in {target}. Use Get data to fetch the files you need."
    outcome["message"] = opened + gate_warning(hooks)
    return outcome
