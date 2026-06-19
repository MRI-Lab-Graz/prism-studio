from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

DATALAD_INSTALL_HINT = "Install with: uv tool install datalad git-annex"
DATALAD_DOCS_URL = "https://www.datalad.org/"


def is_datalad_dataset(project_root: Path) -> bool:
    root = Path(project_root)
    return (root / ".datalad").exists()


def resolve_datalad_executable() -> str:
    return str(shutil.which("datalad") or "").strip()


def run_datalad_get_recursive(
    project_root: Path,
    *,
    datalad_executable: str = "",
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    return run_datalad_get_paths(
        project_root,
        paths=["."],
        datalad_executable=datalad_executable,
        timeout_seconds=timeout_seconds,
        recursive=True,
        no_data=False,
    )


def run_datalad_get_paths(
    project_root: Path,
    *,
    paths: Sequence[str],
    datalad_executable: str = "",
    timeout_seconds: int = 900,
    recursive: bool = False,
    no_data: bool = False,
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

        detail = (process.stderr or process.stdout or "").strip()
        return (False, detail or "Unknown DataLad error.")

    for chunk in target_chunks:
        active_command = [*base_command, "--on-failure", "ignore", *chunk]
        ok, error_message = _run_get_command(active_command)

        if (
            not ok
            and no_data
            and any(
                fragment in str(error_message).lower()
                for fragment in (
                    "unknown argument: -n",
                    "unrecognized arguments: -n",
                    "unknown option: -n",
                )
            )
        ):
            active_command = [
                *_without_no_data_flag(base_command),
                "--on-failure",
                "ignore",
                *chunk,
            ]
            ok, error_message = _run_get_command(active_command)

        if (
            not ok
            and "--on-failure" in str(error_message).lower()
            and (
                "unknown argument" in str(error_message).lower()
                or "unrecognized arguments" in str(error_message).lower()
            )
        ):
            active_command = [*(
                _without_no_data_flag(base_command)
                if no_data else base_command
            ), *chunk]
            ok, error_message = _run_get_command(active_command)

        if not ok:
            error_messages.append(str(error_message))

    result["attempted"] = True
    result["command"] = " && ".join(attempted_commands)

    if not error_messages:
        result["success"] = True
        result["message"] = "DataLad get completed for requested targets."
        return result

    result["message"] = f"DataLad get failed: {error_messages[-1]}"
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


def run_datalad_run(
    project_root: Path,
    *,
    message: str,
    command: Sequence[str],
    datalad_executable: str = "",
    timeout_seconds: int = 1800,
    env: Mapping[str, str] | None = None,
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
    datalad_command = [resolved, "run", "-m", run_message, "--", *escaped_command]
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
) -> dict[str, Any]:
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
    command.extend(["-m", save_message])

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
    sibling_name: str = "ria-store",
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

    name = str(sibling_name or "").strip() or "ria-store"
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


def run_datalad_create_sibling_ria(
    project_root: Path,
    *,
    ria_url: str,
    sibling_name: str = "ria-store",
    alias: str = "",
    recursive: bool = True,
    existing: str = "reconfigure",
    new_store_ok: bool = True,
    datalad_executable: str = "",
    timeout_seconds: int = 600,
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

    url = str(ria_url or "").strip()
    if not url:
        result["message"] = "No RIA store URL was provided."
        return result

    name = str(sibling_name or "").strip() or "ria-store"
    command = [resolved, "create-sibling-ria", url, "-s", name, "--existing", str(existing or "reconfigure")]
    if recursive:
        command.append("-r")
    if new_store_ok:
        command.append("--new-store-ok")
    if str(alias or "").strip():
        command.extend(["--alias", str(alias).strip()])

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
            f"DataLad create-sibling-ria timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad create-sibling-ria failed ({type(exc).__name__}: {exc})."
        return result

    result["stdout"] = process.stdout or ""
    result["stderr"] = process.stderr or ""

    if process.returncode == 0:
        result["success"] = True
        result["message"] = "DataLad RIA sibling created/reconfigured."
        return result

    detail = (process.stderr or process.stdout or "").strip()
    result["message"] = f"DataLad create-sibling-ria failed: {detail or 'Unknown DataLad error.'}"
    return result


def run_datalad_push(
    project_root: Path,
    *,
    sibling_name: str = "ria-store",
    recursive: bool = True,
    data: str = "anything",
    since: str = "",
    datalad_executable: str = "",
    timeout_seconds: int = 7200,
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

    name = str(sibling_name or "").strip() or "ria-store"
    command = [resolved, "push", "--to", name]
    if recursive:
        command.append("-r")
    command.extend(["--data", str(data or "anything")])
    if str(since or "").strip():
        command.extend(["--since", str(since).strip()])

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
            f"DataLad push timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad push failed ({type(exc).__name__}: {exc})."
        return result

    result["stdout"] = process.stdout or ""
    result["stderr"] = process.stderr or ""

    combined = f"{result['stdout']}\n{result['stderr']}".lower()
    has_failure_marker = "(failed)" in combined or "error(" in combined or " error " in combined

    if process.returncode == 0 and not has_failure_marker:
        result["success"] = True
        result["message"] = "DataLad push completed."
        return result

    detail = (result["stderr"] or result["stdout"]).strip()
    result["message"] = f"DataLad push failed: {detail or 'Unknown DataLad error.'}"
    return result


def run_datalad_push_verify(
    project_root: Path,
    *,
    sibling_name: str = "ria-store",
    dataset_roots: Sequence[Path],
    datalad_executable: str = "",
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """Confirm every annexed key in each dataset root is present on the sibling.

    `datalad push` can report per-path failures on a recursive multi-dataset
    push without setting a non-zero exit code, so success must be confirmed
    independently rather than trusting the push's own return code.

    A RIA sibling is actually a pair: `<name>` (plain git remote, no annex
    content) and `<name>-storage` (the ORA special remote that actually
    holds annexed content). `git annex find --not --in` needs a remote
    git-annex can resolve a UUID for, which only the storage sibling has, so
    content presence must be checked against `<name>-storage`.
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

    name = str(sibling_name or "").strip() or "ria-store"
    storage_name = f"{name}-storage"
    git_executable = str(shutil.which("git") or "git")
    result["attempted"] = True

    all_unverified: list[str] = []
    per_dataset: list[dict[str, Any]] = []

    for dataset_root in dataset_roots:
        root = Path(dataset_root)
        command = [git_executable, "annex", "find", "--not", "--in", storage_name]
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


def run_datalad_remove_sibling(
    project_root: Path,
    *,
    sibling_name: str = "ria-store",
    dataset_roots: Sequence[Path],
    mark_annex_dead: bool = False,
    datalad_executable: str = "",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "per_dataset": [],
        "message": "",
    }
    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    name = str(sibling_name or "").strip() or "ria-store"
    storage_name = f"{name}-storage"
    result["attempted"] = True

    def _run(command: list[str], cwd: Path) -> tuple[bool, str]:
        try:
            process = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, f"timed out after {max(1, int(timeout_seconds))} seconds."
        except Exception as exc:
            return False, f"failed ({type(exc).__name__}: {exc})."
        if process.returncode == 0:
            return True, (process.stdout or "").strip()
        return False, (process.stderr or process.stdout or "").strip() or "Unknown DataLad error."

    per_dataset: list[dict[str, Any]] = []
    for dataset_root in dataset_roots:
        root = Path(dataset_root)
        entry: dict[str, Any] = {"path": str(root), "success": False, "message": ""}

        ok, detail = _run([resolved, "siblings", "remove", "-s", name], root)
        if not ok:
            ok, detail = _run(["git", "remote", "remove", name], root)

        # A RIA sibling is a pair: `<name>` (git) and `<name>-storage` (the
        # ORA special remote holding annexed content). Both must be removed
        # for the dataset to have no remaining connection to the store.
        storage_ok, storage_detail = _run(
            [resolved, "siblings", "remove", "-s", storage_name], root
        )
        if not storage_ok:
            storage_ok, storage_detail = _run(["git", "remote", "remove", storage_name], root)

        entry["success"] = ok and storage_ok
        entry["message"] = "; ".join(
            part for part in (detail, storage_detail) if part
        ) or ("Sibling removed." if entry["success"] else "Failed to remove sibling.")

        if ok and mark_annex_dead:
            git_executable = str(shutil.which("git") or "git")
            dead_ok, dead_detail = _run([git_executable, "annex", "dead", "here"], root)
            entry["annex_dead"] = dead_ok
            if not dead_ok:
                entry["message"] += f" (git annex dead failed: {dead_detail})"

        per_dataset.append(entry)

    result["per_dataset"] = per_dataset
    result["success"] = all(entry["success"] for entry in per_dataset)
    failed_paths = [entry["path"] for entry in per_dataset if not entry["success"]]
    result["message"] = (
        "Sibling removed from all dataset roots."
        if result["success"]
        else f"Failed to remove sibling from: {', '.join(failed_paths)}"
    )
    return result


def run_datalad_upload_to_ria(
    project_root: Path,
    *,
    dataset_roots: Sequence[Path],
    ria_url: str,
    sibling_name: str = "ria-store",
    alias: str = "",
    keep_sibling: bool = False,
    mark_annex_dead: bool = False,
    datalad_executable: str = "",
    progress_callback: Any = None,
    is_cancelled: Any = None,
) -> dict[str, Any]:
    """Orchestrate create-sibling -> push -> verify -> (optional) disconnect.

    The disconnect step only runs when verification confirms every annexed
    key reached the sibling; otherwise the sibling is left registered so a
    retry can resume the incomplete push.
    """
    resolved = str(datalad_executable or resolve_datalad_executable()).strip()

    def _report(percent: int, message: str) -> None:
        if callable(progress_callback):
            progress_callback(percent, message)

    def _cancelled() -> bool:
        return bool(callable(is_cancelled) and is_cancelled())

    result: dict[str, Any] = {
        "success": False,
        "sibling_created": False,
        "pushed": False,
        "verified": False,
        "disconnected": False,
        "kept_sibling": keep_sibling,
        "message": "",
        "create": None,
        "push": None,
        "verify": None,
        "disconnect": None,
    }

    if not resolved:
        result["message"] = (
            "DataLad executable is not available in this environment. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return result

    if _cancelled():
        result["message"] = "Cancelled before starting."
        return result

    _report(5, "Creating/reconfiguring RIA sibling...")
    create_result = run_datalad_create_sibling_ria(
        project_root,
        ria_url=ria_url,
        sibling_name=sibling_name,
        alias=alias,
        datalad_executable=resolved,
    )
    result["create"] = create_result
    if not create_result.get("success"):
        result["message"] = f"Could not create RIA sibling: {create_result.get('message')}"
        return result
    result["sibling_created"] = True

    if _cancelled():
        result["message"] = "Cancelled after sibling creation; sibling left registered."
        return result

    _report(30, "Pushing dataset to RIA store...")
    push_result = run_datalad_push(
        project_root,
        sibling_name=sibling_name,
        datalad_executable=resolved,
    )
    result["push"] = push_result
    if not push_result.get("success"):
        result["message"] = f"Push failed: {push_result.get('message')}"
        return result
    result["pushed"] = True

    if _cancelled():
        result["message"] = "Cancelled after push; sibling left registered."
        return result

    _report(70, "Verifying all content reached the RIA store...")
    verify_result = run_datalad_push_verify(
        project_root,
        sibling_name=sibling_name,
        dataset_roots=dataset_roots,
        datalad_executable=resolved,
    )
    result["verify"] = verify_result
    result["verified"] = bool(verify_result.get("verified"))
    if not result["verified"]:
        result["message"] = (
            f"Push could not be verified: {verify_result.get('message')}. "
            "Sibling left registered for retry."
        )
        return result

    if keep_sibling:
        result["success"] = True
        result["message"] = "Push verified. Sibling kept registered as requested."
        return result

    if _cancelled():
        result["message"] = "Cancelled after verification; sibling left registered."
        return result

    _report(90, "Disconnecting local sibling...")
    disconnect_result = run_datalad_remove_sibling(
        project_root,
        sibling_name=sibling_name,
        dataset_roots=dataset_roots,
        mark_annex_dead=mark_annex_dead,
        datalad_executable=resolved,
    )
    result["disconnect"] = disconnect_result
    result["disconnected"] = bool(disconnect_result.get("success"))
    if not result["disconnected"]:
        result["message"] = f"Verified push, but disconnect failed: {disconnect_result.get('message')}"
        return result

    _report(100, "Upload verified and sibling disconnected.")
    result["success"] = True
    result["message"] = "Push verified and local sibling disconnected."
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
