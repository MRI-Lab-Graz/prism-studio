from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.datalad_doctor import install_hint

_GET_ERROR_PATH_RE = re.compile(r"^(?:get|install)\(error\):\s*(\S+)", re.MULTILINE)


def _extract_get_error_paths(detail: str) -> list[str]:
    """Pull the specific target paths DataLad reported as failed out of a
    `get`/`install` failure's combined stdout+stderr, e.g.
    "get(error): sub-01/foo.nii.gz (file) [not available]"."""
    return _GET_ERROR_PATH_RE.findall(detail)

DATALAD_INSTALL_HINT = install_hint()
SAVE_GATE_MARKER = "PRISM save gate"
DATALAD_DOCS_URL = "https://www.datalad.org/"


def is_datalad_dataset(project_root: Path) -> bool:
    root = Path(project_root)
    return (root / ".datalad").exists()


def resolve_datalad_executable() -> str:
    return str(shutil.which("datalad") or "").strip()


def paths_have_uncommitted_changes(
    project_root: Path,
    *,
    paths: Sequence[str] | None = None,
    timeout_seconds: int = 120,
) -> bool:
    """Return True if `git status --porcelain` reports anything under paths
    (the whole tree, if paths is empty/None).

    `datalad save` always exits 0 whether or not there was anything to save
    (confirmed empirically -- it never reliably signals "no changes" via
    exit code or a message), so it cannot be used to tell "a mutation
    partially happened before failing" apart from "nothing happened at all".
    This checks the actual working tree instead. Fails safe (returns True)
    on any error, so an undetermined state is never mistaken for "clean".
    """
    root = Path(project_root)
    git_executable = str(shutil.which("git") or "git")
    normalized_paths = [
        str(Path(str(path or "").strip()).as_posix())
        for path in (paths or [])
        if str(path or "").strip()
    ]
    command = [git_executable, "status", "--porcelain"]
    if normalized_paths:
        command.extend(["--", *normalized_paths])
    try:
        process = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except Exception:
        return True
    if process.returncode != 0:
        return True
    return bool((process.stdout or "").strip())


def run_datalad_get_paths(
    project_root: Path,
    *,
    paths: Sequence[str],
    datalad_executable: str = "",
    timeout_seconds: int = 900,
    recursive: bool = False,
    no_data: bool = False,
    jobs: int = 0,
) -> dict[str, Any]:
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "command": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    normalized_paths = [
        str(Path(str(path or "").strip()).as_posix())
        for path in paths
        if str(path or "").strip()
    ]
    if not normalized_paths:
        result["success"] = True
        result["message"] = "No DataLad get targets were requested."
        return result

    base_command = [resolved, "get"]
    if recursive:
        base_command.append("-r")
    if no_data:
        base_command.append("-n")
    if jobs and int(jobs) > 1:
        # Lets git-annex fetch multiple files concurrently within this one
        # `get` invocation (e.g. multiple subjects' content from the same
        # remote at once), instead of one file/dataset at a time.
        base_command.extend(["-J", str(int(jobs))])

    # Keep command lengths stable for many target paths.
    target_chunks = [
        normalized_paths[index:index + 200]
        for index in range(0, len(normalized_paths), 200)
    ]

    attempted_commands: list[str] = []
    error_messages: list[str] = []

    def _without_no_data_flag(command: list[str]) -> list[str]:
        return [part for part in command if part != "-n"]

    def _run_get_command(command: list[str]) -> tuple[bool, str]:
        attempted_commands.append(shlex.join(command))
        try:
            process = subprocess.run(
                command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (
                False,
                f"DataLad get timed out after {max(1, int(timeout_seconds))} seconds.",
            )
        except Exception as exc:
            return (False, f"DataLad get failed ({type(exc).__name__}: {exc}).")

        if process.returncode == 0:
            return (True, "")

        # DataLad routinely logs routine `[INFO]` lines to stderr even on
        # failure, while the actual per-file `get(error): ... [not
        # available]` reasons land on stdout — combine both so a non-empty
        # stderr never hides the real error on stdout.
        detail = "\n".join(
            part.strip() for part in (process.stdout, process.stderr) if part and part.strip()
        )
        return (False, detail or "Unknown DataLad error.")

    # No `--on-failure`: it is a global DataLad option that `get` rejects, and `ignore` would hide failures anyway.
    for chunk in target_chunks:
        ok, error_message = _run_get_command([*base_command, "--", *chunk])

        if not ok and no_data and any(
            fragment in str(error_message).lower()
            for fragment in ("unknown argument: -n", "unrecognized arguments: -n", "unknown option: -n")
        ):
            base_command = _without_no_data_flag(base_command)
            ok, error_message = _run_get_command([*base_command, "--", *chunk])

        if not ok:
            error_messages.append(str(error_message))

    result["attempted"] = True
    result["command"] = " && ".join(attempted_commands)

    if not error_messages:
        result["success"] = True
        result["message"] = "DataLad get completed for requested targets."
        return result

    combined_detail = "\n".join(error_messages)
    result["message"] = f"DataLad get failed: {combined_detail}"
    result["failed_paths"] = sorted(set(_extract_get_error_paths(combined_detail)))
    return result


def run_datalad_unlock(
    project_root: Path,
    *,
    paths: Sequence[str],
    datalad_executable: str = "",
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Best-effort `datalad unlock` so annexed files become writable copies.

    Annexed files are normally read-only symlinks; in-place content edits
    (e.g. rewriting subject IDs inside a .tsv/.json) fail with
    PermissionError unless the file is unlocked first. Unlocking a file that
    isn't annexed is a harmless no-op, so any outcome short of a hard
    execution failure is treated as success here — the goal is "best effort
    make writable," not a strict precondition.
    """
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "command": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    normalized_paths = [
        str(Path(str(path or "").strip()).as_posix())
        for path in paths
        if str(path or "").strip()
    ]
    if not normalized_paths:
        result["success"] = True
        result["message"] = "No DataLad unlock targets were requested."
        return result

    # Note: unlike `get`/`save`, `datalad unlock` does not accept
    # `--on-failure` — passing it makes argparse reject the whole command
    # and print usage text instead of unlocking anything.
    command = [resolved, "unlock", *normalized_paths]
    result["attempted"] = True
    result["command"] = shlex.join(command)

    try:
        process = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["message"] = (
            f"DataLad unlock timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad unlock failed ({type(exc).__name__}: {exc})."
        return result

    result["success"] = True
    detail = (process.stdout or process.stderr or "").strip()
    result["message"] = detail or "DataLad unlock completed."
    return result


def run_datalad_run(project_root: Path, *, command: Sequence[str], **kwargs: Any) -> dict[str, Any]:
    """`datalad run`, with `python -c <script>` turned into `python <script file>`.

    DataLad joins the command into one shell command line (cmd.exe on Windows,
    where & | % ^ are live) and callers embed project paths and filter values in
    the -c script. In a file those values never touch a shell. The file lives in
    `.git/` (untracked, so the run's change set stays clean) and is removed after.
    """
    root = Path(project_root)
    parts = [str(part) for part in command]
    script_file = None
    if len(parts) >= 3 and parts[1] == "-c" and (root / ".git").is_dir():
        script_file = root / ".git" / f"prism_run_{secrets.token_hex(8)}.py"
        script_file.write_text(parts[2], encoding="utf-8")
        parts = [parts[0], script_file.relative_to(root).as_posix(), *parts[3:]]
    try:
        return _run_datalad_run(root, command=parts, **kwargs)
    finally:
        if script_file is not None:
            script_file.unlink(missing_ok=True)


def _run_datalad_run(
    project_root: Path,
    *,
    message: str,
    command: Sequence[str],
    datalad_executable: str = "",
    timeout_seconds: int = 1800,
    env: Mapping[str, str] | None = None,
    explicit: bool = False,
    outputs: Sequence[str] = (),
) -> dict[str, Any]:
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "command": "",
        "stdout": "",
        "stderr": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    normalized_command = [str(part) for part in command]
    if not normalized_command:
        result["message"] = "DataLad run command is empty."
        return result

    # `datalad run` treats the command after `--` as a template supporting
    # placeholders like {inputs}/{outputs}. Any literal curly brace in the
    # command (e.g. a Python dict/set literal embedded in a -c script) must
    # be escaped by doubling, exactly like Python's str.format(), or DataLad
    # rejects it outright as an "unrecognized placeholder" before running
    # anything.
    escaped_command = [
        part.replace("{", "{{").replace("}", "}}") for part in normalized_command
    ]

    run_message = str(message or "").strip() or "PRISM: tracked edit"
    run_flags: list[str] = []
    if explicit:
        run_flags.append("--explicit")
        for path in outputs:
            run_flags.extend(["-o", str(path)])
    datalad_command = [resolved, "run", *run_flags, f"--message={run_message}", "--", *escaped_command]
    result["attempted"] = True
    result["command"] = shlex.join(datalad_command)

    run_env = os.environ.copy()
    if env:
        run_env.update({str(key): str(value) for key, value in env.items()})

    try:
        process = subprocess.run(
            datalad_command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
            env=run_env,
        )
    except subprocess.TimeoutExpired:
        result["message"] = (
            f"DataLad run timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad run failed ({type(exc).__name__}: {exc})."
        return result

    result["stdout"] = process.stdout or ""
    result["stderr"] = process.stderr or ""

    if process.returncode == 0:
        result["success"] = True
        result["message"] = "DataLad run completed successfully."
        return result

    detail = (process.stderr or process.stdout or "").strip()
    result["message"] = f"DataLad run failed: {detail or 'Unknown DataLad error.'}"
    return result


def run_datalad_save(
    project_root: Path,
    *,
    message: str,
    datalad_executable: str = "",
    timeout_seconds: int = 900,
    recursive: bool = True,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    """Run `datalad save`.

    paths: when given, scopes the save (and its recursion, if `recursive`) to
    just those paths instead of the whole dataset. With no paths, `-r` walks
    *every* registered subdataset on *every* call -- fine for a one-off save,
    but ruinous when called once per subject/item in a loop over a dataset
    with many nested subdatasets (each call re-scans all of them, not just
    the one that actually changed).
    """
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "no_changes": False,
        "command": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    save_message = str(message or "").strip() or "PRISM: autosave pending changes"
    command = [resolved, "save"]
    if recursive:
        command.append("-r")
    command.append(f"--message={save_message}")  # "--message=..." so a text starting with "-" is not an option
    normalized_paths = sorted({str(p).strip() for p in (paths or []) if str(p).strip()})
    if normalized_paths:
        command.append("--")
        command.extend(normalized_paths)

    result["attempted"] = True
    result["command"] = shlex.join(command)

    try:
        process = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["message"] = (
            f"DataLad save timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad save failed ({type(exc).__name__}: {exc})."
        return result

    if process.returncode == 0:
        result["success"] = True
        result["message"] = "DataLad save completed."
        return result

    detail = (process.stderr or process.stdout or "").strip()
    if "nothing to save" in detail.lower():
        result["success"] = True
        result["no_changes"] = True
        result["message"] = "No pending DataLad changes."
        return result

    result["message"] = f"DataLad save failed: {detail or 'Unknown DataLad error.'}"
    return result


def run_datalad_sibling_exists(
    project_root: Path,
    *,
    sibling_name: str = "origin",
    datalad_executable: str = "",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "exists": False,
        "command": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    name = str(sibling_name or "").strip() or "origin"
    command = [resolved, "siblings", "-s", name]
    result["attempted"] = True
    result["command"] = shlex.join(command)

    try:
        process = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["message"] = (
            f"DataLad siblings query timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad siblings query failed ({type(exc).__name__}: {exc})."
        return result

    result["success"] = True
    output = (process.stdout or "").strip()
    result["exists"] = process.returncode == 0 and name in output
    result["message"] = output or "DataLad siblings query completed."
    return result


def _run_streaming_command(
    command: list[str],
    *,
    cwd: str,
    timeout_seconds: int,
    line_callback: Any = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a command with merged stdout+stderr, streaming each line to
    `line_callback` (if given) as it's produced.

    Recursive DataLad operations (`create-sibling -r`, `push -r`) across a
    project with 100+ nested subdatasets can run for many minutes; without
    this, a caller using `subprocess.run` only sees output after the whole
    thing exits, leaving the UI/terminal looking dead the entire time.

    Returns `{"returncode": int, "output": str}` on completion. Raises
    `subprocess.TimeoutExpired` on timeout (mirroring `subprocess.run`'s own
    contract) so callers can build their own timeout message; raises the
    original exception for any other failure to start the process.
    """
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    output_lines: list[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            stripped = line.rstrip()
            if stripped and callable(line_callback):
                line_callback(stripped)
        process.wait(timeout=max(1, int(timeout_seconds)))
    except subprocess.TimeoutExpired:
        process.kill()
        raise
    return {"returncode": process.returncode, "output": "".join(output_lines)}


_SIBLING_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def sibling_label_problem(label: str, what: str) -> str:
    """'' for a plain label (git remote name / store alias), else why it is refused."""
    if _SIBLING_LABEL.fullmatch(str(label or "")):
        return ""
    return f"The {what} must be a plain label: letters, digits, '.', '_' and '-' only (at most 64, not starting with a symbol)."


def run_datalad_create_sibling_plain(
    project_root: Path,
    *,
    remote_url: str,
    sibling_name: str = "server",
    recursive: bool = True,
    existing: str = "reconfigure",
    datalad_executable: str = "",
    timeout_seconds: int = 600,
    line_callback: Any = None,
) -> dict[str, Any]:
    """Create/reconfigure a plain DataLad sibling over SSH or a local path.

    An ordinary repository with its annexed content pushed straight into it.

    With `recursive=True` this recurses into every nested subdataset
    internally (a single DataLad invocation, not one per subdataset), which
    can take minutes on a project with 100+ subjects -- `line_callback`, if
    given, receives each output line as DataLad produces it, e.g. for live
    terminal progress instead of the process looking dead until it exits.
    """
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "command": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    url = str(remote_url or "").strip()
    if not url:
        result["message"] = "No remote sibling URL was provided."
        return result
    if url.startswith("-"):
        result["message"] = "Refusing a URL that starts with '-'."
        return result

    name = str(sibling_name or "").strip() or "server"
    if problem := sibling_label_problem(name, "sibling name"):
        result["message"] = problem
        return result
    command = [
        resolved,
        "create-sibling",
        url,
        "-s",
        name,
        "--existing",
        str(existing or "reconfigure"),
    ]
    if recursive:
        command.append("-r")

    result["attempted"] = True
    result["command"] = shlex.join(command)

    try:
        run_result = _run_streaming_command(
            command,
            cwd=str(root),
            timeout_seconds=timeout_seconds,
            line_callback=line_callback,
        )
    except subprocess.TimeoutExpired:
        result["message"] = (
            f"DataLad create-sibling timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad create-sibling failed ({type(exc).__name__}: {exc})."
        return result

    result["stdout"] = run_result["output"]
    result["stderr"] = ""

    if run_result["returncode"] == 0:
        result["success"] = True
        result["message"] = "DataLad sibling created/reconfigured."
        return result

    detail = run_result["output"].strip()
    result["message"] = f"DataLad create-sibling failed: {detail or 'Unknown DataLad error.'}"
    return result


def run_datalad_push(
    project_root: Path,
    *,
    sibling_name: str = "origin",
    recursive: bool = True,
    data: str = "anything",
    since: str = "",
    datalad_executable: str = "",
    timeout_seconds: int = 7200,
    line_callback: Any = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """See `run_datalad_create_sibling_plain` for the `line_callback`
    contract. `env` is the child's environment (None: inherit). `push -r` across 100+ subdatasets with real annexed content is
    the single longest-running step in the sync/finalize flow -- this is
    where live progress matters most."""
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "command": "",
        "stdout": "",
        "stderr": "",
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    name = str(sibling_name or "").strip() or "origin"
    command = [resolved, "push", "--to", name]
    if recursive:
        command.append("-r")
    command.extend(["--data", str(data or "anything")])
    if str(since or "").strip():
        command.extend(["--since", str(since).strip()])

    result["attempted"] = True
    result["command"] = shlex.join(command)

    try:
        run_result = _run_streaming_command(
            command,
            cwd=str(root),
            timeout_seconds=timeout_seconds,
            line_callback=line_callback,
            env=env,
        )
    except subprocess.TimeoutExpired:
        result["message"] = (
            f"DataLad push timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad push failed ({type(exc).__name__}: {exc})."
        return result

    result["stdout"] = run_result["output"]
    result["stderr"] = ""

    combined = result["stdout"].lower()
    has_failure_marker = "(failed)" in combined or "error(" in combined or " error " in combined

    if run_result["returncode"] == 0 and not has_failure_marker:
        result["success"] = True
        result["message"] = "DataLad push completed."
        return result

    detail = result["stdout"].strip()
    result["message"] = f"DataLad push failed: {detail or 'Unknown DataLad error.'}"
    return result


def run_datalad_update(
    project_root: Path,
    *,
    sibling_name: str = "origin",
    datalad_executable: str = "",
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Bring in what the server has saved, fast-forward only: it never merges, so it cannot mix two people's work."""
    root = Path(project_root)
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {"success": False, "command": "", "output": "", "message": ""}
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    name = str(sibling_name or "").strip() or "origin"
    command = [resolved, "update", "-s", name, "--how", "ff-only", "-r"]
    result["command"] = shlex.join(command)
    try:
        run_result = _run_streaming_command(command, cwd=str(root), timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired:
        result["message"] = f"DataLad update timed out after {max(1, int(timeout_seconds))} seconds."
        return result
    except Exception as exc:
        result["message"] = f"DataLad update failed ({type(exc).__name__}: {exc})."
        return result

    result["output"] = run_result["output"]
    lowered = result["output"].lower()
    if run_result["returncode"] == 0 and "(impossible)" not in lowered and "(error)" not in lowered:
        result["success"] = True
        result["message"] = "DataLad update completed."
        return result
    result["message"] = f"DataLad update failed: {result['output'].strip() or 'Unknown DataLad error.'}"
    return result


def run_datalad_clone(
    location: str,
    target: Path,
    *,
    datalad_executable: str = "",
    timeout_seconds: int = 3600,
    line_callback: Any = None,
) -> dict[str, Any]:
    """`datalad clone <location> <target>`: the dataset itself, the source as `origin`; nested datasets are not touched.

    `location` must already have passed `share_publish.location_problem`; `target` must be an absolute path.
    """
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {"success": False, "command": "", "output": "", "message": ""}
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result
    target = Path(target)
    return _run_datalad_step(
        result, [resolved, "clone", str(location), str(target)], str(target.parent), timeout_seconds, line_callback
    )


def run_datalad_install_nested(
    dataset_root: Path,
    paths: Sequence[str],
    *,
    datalad_executable: str = "",
    timeout_seconds: int = 3600,
    line_callback: Any = None,
) -> dict[str, Any]:
    """`datalad get -n <paths>`: install these nested datasets of `dataset_root` (one level, no -r), without data.

    The paths (and the urls behind them) must already be checked by the caller.
    """
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {"success": False, "command": "", "output": "", "message": ""}
    if not resolved:
        result["message"] = f"DataLad executable is not available in this environment. {DATALAD_INSTALL_HINT}."
        return result
    return _run_datalad_step(
        result, [resolved, "get", "-n", *paths], str(dataset_root), timeout_seconds, line_callback
    )


def _run_datalad_step(result: dict, command: list[str], cwd: str, timeout_seconds: int, line_callback: Any) -> dict:
    """Run `datalad <verb> ...` for open-from-server.

    For a folder location, DataLad would also add the server's own `origin` (from its uncommitted .git/config,
    untrusted) as `origin-2` and fetch it; inherit-local-origin=false stops that for this command.
    """
    run = [command[0], "-c", "datalad.install.inherit-local-origin=false", *command[1:]]
    result["command"] = shlex.join(run)
    try:
        run_result = _run_streaming_command(run, cwd=cwd, timeout_seconds=timeout_seconds, line_callback=line_callback)
    except subprocess.TimeoutExpired:
        result["message"] = f"DataLad {command[1]} timed out after {max(1, int(timeout_seconds))} seconds."
        return result
    except Exception as exc:
        result["message"] = f"DataLad {command[1]} failed ({type(exc).__name__}: {exc})."
        return result
    result["output"] = run_result["output"]
    if run_result["returncode"] != 0:
        result["message"] = f"DataLad {command[1]} failed: {run_result['output'].strip() or 'Unknown DataLad error.'}"
        return result
    result["success"] = True
    result["message"] = f"DataLad {command[1]} completed."
    return result


def run_datalad_push_verify(
    project_root: Path,
    *,
    sibling_name: str = "origin",
    dataset_roots: Sequence[Path],
    datalad_executable: str = "",
    timeout_seconds: int = 1800,
    line_callback: Any = None,
) -> dict[str, Any]:
    """Confirm every annexed key in each dataset root is present on the sibling.

    `datalad push` can report per-path failures on a recursive multi-dataset
    push without setting a non-zero exit code, so success must be confirmed
    independently rather than trusting the push's own return code.

    Content is pushed directly to the sibling `<name>`, so that is the remote checked.

    Unlike `run_datalad_push`/`run_datalad_create_sibling_plain`, this already
    loops per dataset root as separate (fast) subprocess calls in our own
    code, so there's no need for line-level Popen streaming -- `line_callback`
    (if given) is simply called once per root with a "checking N/M" message,
    which is enough to show live progress across a 100+-subdataset project.
    """
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "verified": False,
        "unverified_paths": [],
        "per_dataset": [],
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    check_name = str(sibling_name or "").strip() or "origin"
    git_executable = str(shutil.which("git") or "git")
    result["attempted"] = True

    all_unverified: list[str] = []
    per_dataset: list[dict[str, Any]] = []
    roots_list = list(dataset_roots)
    total_roots = len(roots_list)

    for index, dataset_root in enumerate(roots_list, start=1):
        root = Path(dataset_root)
        if callable(line_callback):
            line_callback(f"Verifying {root.name or root} ({index}/{total_roots})...")
        command = [git_executable, "annex", "find", "--not", "--in", check_name]
        entry: dict[str, Any] = {
            "path": str(root),
            "command": shlex.join(command),
            "success": False,
            "unverified_paths": [],
            "message": "",
        }
        try:
            process = subprocess.run(
                command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            entry["message"] = (
                f"DataLad annex find timed out after {max(1, int(timeout_seconds))} seconds."
            )
            per_dataset.append(entry)
            continue
        except Exception as exc:
            entry["message"] = f"DataLad annex find failed ({type(exc).__name__}: {exc})."
            per_dataset.append(entry)
            continue

        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "").strip()
            entry["message"] = f"DataLad annex find failed: {detail or 'Unknown DataLad error.'}"
            per_dataset.append(entry)
            continue

        outstanding = [line.strip() for line in (process.stdout or "").splitlines() if line.strip()]
        entry["success"] = True
        entry["unverified_paths"] = outstanding
        entry["message"] = (
            "All annexed content present on sibling."
            if not outstanding
            else f"{len(outstanding)} annexed file(s) missing on sibling."
        )
        per_dataset.append(entry)
        all_unverified.extend(f"{root}: {path}" for path in outstanding)

    result["per_dataset"] = per_dataset
    result["unverified_paths"] = all_unverified
    every_dataset_checked = all(entry["success"] for entry in per_dataset)
    result["success"] = every_dataset_checked
    result["verified"] = every_dataset_checked and not all_unverified
    result["message"] = (
        "Push verified: all annexed content is present on the sibling."
        if result["verified"]
        else f"Push not fully verified: {len(all_unverified)} unresolved file(s)."
        if every_dataset_checked
        else "Push verification could not complete for one or more dataset roots."
    )
    return result


def parse_json_from_output(output_text: str) -> dict[str, Any] | None:
    text = str(output_text or "")
    if not text.strip():
        return None

    for raw_line in reversed(text.splitlines()):
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload

    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
