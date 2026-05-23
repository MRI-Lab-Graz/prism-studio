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

    command = [resolved, "get", "-r", "--on-failure", "ignore", "."]
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
            f"DataLad get timed out after {max(1, int(timeout_seconds))} seconds."
        )
        return result
    except Exception as exc:
        result["message"] = f"DataLad get failed ({type(exc).__name__}: {exc})."
        return result

    if process.returncode == 0:
        result["success"] = True
        result["message"] = "DataLad recursive get completed for project scope."
        return result

    detail = (process.stderr or process.stdout or "").strip()
    result["message"] = f"DataLad get failed: {detail or 'Unknown DataLad error.'}"
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

    run_message = str(message or "").strip() or "PRISM: tracked edit"
    datalad_command = [resolved, "run", "-m", run_message, "--", *normalized_command]
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
