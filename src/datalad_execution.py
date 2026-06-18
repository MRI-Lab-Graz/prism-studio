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
