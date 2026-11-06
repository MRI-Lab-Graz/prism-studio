"""Get data: fetch the annexed content of your own copy from the server, with the export's filters.

``prism_tools datalad get-data`` and Studio's "Get data" call :func:`get_data`. Everything is fetched unless the
filters (the export's: subjects, sessions, modalities, acq, task, and which top-level folders come along) leave it out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from src.datalad_clone import gate_warning, install_nested_checked
from src.datalad_execution import is_datalad_dataset, run_datalad_get_paths
from src.datalad_state import SERVER, _reachable
from src.export_selection import select_content_paths, select_scope_dirs
from src.share_publish import _git, has_sibling

GET_DATA_TIMEOUT_SECONDS = 6 * 3600  # per chunk of 200 files; large MRI sets over a slow link take long
LISTED_FAILURES = 20


def _result(success: bool, message: str, **extra) -> dict:
    return {"success": success, "message": message, **extra}


def filters_from_options(data: dict) -> dict:
    """The filters of an export options dict (what Studio sends, what ``export_data_from_args`` builds), with its defaults."""
    from src.export_options import normalize_scope_grouped_labels, normalize_scope_labels

    return {
        "include_derivatives": bool(data.get("include_derivatives", True)),
        "include_sourcedata": bool(data.get("include_sourcedata", False)),
        "include_code": bool(data.get("include_code", True)),
        "include_analysis": bool(data.get("include_analysis", False)),
        "exclude_subjects": normalize_scope_labels(data.get("exclude_subjects")),
        "exclude_sessions": normalize_scope_labels(data.get("exclude_sessions")),
        "exclude_modalities": normalize_scope_labels(data.get("exclude_modalities")),
        "exclude_acq": normalize_scope_grouped_labels(data.get("exclude_acq")),
        "exclude_tasks": normalize_scope_grouped_labels(data.get("exclude_tasks")),
    }


def get_data(
    project_root, *, sibling_name: Optional[str] = None, line_callback: Optional[Callable[[str], None]] = None, **filters
) -> dict:
    """Fetch the content of the files the filters keep. ``filters`` are those of ``select_content_paths``."""
    say = line_callback or (lambda _line: None)
    root = Path(project_root)
    server = sibling_name or SERVER
    filters = {**filters_from_options({}), **filters}  # a direct call equals the command and Studio: the export's defaults

    if not is_datalad_dataset(root) or not has_sibling(root, server):
        others = [f"Server found as '{name}'. Use --sibling-name {name}." for name in _git(root, "remote").split()]
        message = " ".join(["This project has no server, so there is nothing to fetch from.", *others])
        return _result(True, message, skipped=True, fetched=0)
    if not _reachable(root, server):
        return _result(False, "The server could not be reached. Check your network connection and try again.")

    say("Looking up which folders the server has...")
    scope = select_scope_dirs(root, **filters)

    def wanted(path: str) -> bool:  # a nested dataset in, above or below a chosen folder
        return any(path == s or s.startswith(path + "/") or path.startswith(s + "/") for s in scope)

    # the nested datasets the server names are untrusted: the checked installer of open from server, never `get -n -r`
    hooks: dict = {"installed": [], "foreign": [], "errors": []}
    problem = install_nested_checked(root, hooks, fresh=False, wanted=wanted, line_callback=line_callback)
    if problem:
        return _result(False, f"Nothing was fetched: {problem}.", fetched=0)

    paths = select_content_paths(root, **filters)
    if not paths:
        return _result(True, "No files match the chosen scope, so nothing was fetched.", fetched=0)

    say(f"Fetching data for {len(paths)} file(s) from the server...")
    got = run_datalad_get_paths(root, paths=paths, jobs=4, timeout_seconds=GET_DATA_TIMEOUT_SECONDS)
    if got.get("success"):
        return _result(
            True, f"Fetched the data of {len(paths)} file(s) from the server." + gate_warning(hooks), fetched=len(paths)
        )

    failed = list(got.get("failed_paths") or [])
    if failed:
        listed = ", ".join(failed[:LISTED_FAILURES]) + (" ..." if len(failed) > LISTED_FAILURES else "")
        message = f"{len(failed)} file(s) could not be fetched; the server does not have them: {listed}"
    else:
        message = "Fetching the data failed: " + (str(got.get("message") or "").strip() or "unknown error.")
    return _result(False, message, fetched=len(paths) - len(failed), failed_paths=failed)
