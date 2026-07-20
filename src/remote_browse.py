"""List/create folders on an SSH-accessible remote server.

Backs the "Browse..." folder picker next to the rsync Destination field and
the plain-SSH-sibling case of the DataLad Server URL field -- both need a
destination folder that may or may not already exist yet on a server the
app already has non-interactive SSH access to (see
`rsync_execution.ensure_remote_directory`, which the same SSH access
pattern already relies on).
"""

from __future__ import annotations

import posixpath
import shlex
import shutil
import subprocess
from typing import Any


def resolve_ssh_executable() -> str:
    return str(shutil.which("ssh") or "").strip()


def list_remote_directory(
    host: str,
    path: str,
    *,
    ssh_executable: str = "",
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    """List subdirectories of `path` on `host` over SSH.

    Only directories are returned (not files), since this backs a
    destination-folder picker rather than a general file browser. Hidden
    (dotfile) directories are skipped, matching the local filesystem
    browser's default behavior.
    """
    resolved = str(ssh_executable or resolve_ssh_executable()).strip()
    result: dict[str, Any] = {
        "success": False,
        "path": None,
        "parent": None,
        "dirs": [],
        "message": "",
    }
    if not resolved:
        result["message"] = "ssh executable is not available in this environment."
        return result

    host = str(host or "").strip()
    if not host:
        result["message"] = "No host was provided."
        return result

    target_path = str(path or "").strip() or "."
    # `cd` both validates the path exists/is accessible and resolves it to
    # an absolute path via `pwd`; `ls -1p` lists one entry per line with a
    # trailing "/" on directories (POSIX-specified, so this works the same
    # on GNU and BSD/macOS remotes).
    remote_command = f"cd -- {shlex.quote(target_path)} && pwd && ls -1p"
    command = [resolved, host, remote_command]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["message"] = f"Listing timed out after {max(1, int(timeout_seconds))} seconds."
        return result
    except Exception as exc:
        result["message"] = f"Listing failed ({type(exc).__name__}: {exc})."
        return result

    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        result["message"] = detail or "Could not list remote directory."
        return result

    lines = (process.stdout or "").splitlines()
    if not lines:
        result["message"] = "Empty response from server."
        return result

    resolved_path = lines[0].strip() or "/"
    dir_names = sorted(
        (line[:-1] for line in lines[1:] if line.endswith("/") and line[:-1] not in (".", "..")),
        key=str.lower,
    )

    parent = posixpath.dirname(resolved_path.rstrip("/")) or "/"
    if parent == resolved_path:
        parent = None

    result["success"] = True
    result["path"] = resolved_path
    result["parent"] = parent
    result["dirs"] = [
        {"name": name, "path": posixpath.join(resolved_path, name)} for name in dir_names
    ]
    return result


def create_remote_directory(
    host: str,
    path: str,
    *,
    ssh_executable: str = "",
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    """Create (`mkdir -p`) a directory on `host` and return its resolved absolute path."""
    resolved = str(ssh_executable or resolve_ssh_executable()).strip()
    result: dict[str, Any] = {"success": False, "path": None, "message": ""}
    if not resolved:
        result["message"] = "ssh executable is not available in this environment."
        return result

    host = str(host or "").strip()
    if not host:
        result["message"] = "No host was provided."
        return result

    target_path = str(path or "").strip()
    if not target_path:
        result["message"] = "No path was provided."
        return result

    remote_command = (
        f"mkdir -p -- {shlex.quote(target_path)} && cd -- {shlex.quote(target_path)} && pwd"
    )
    command = [resolved, host, remote_command]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["message"] = f"mkdir timed out after {max(1, int(timeout_seconds))} seconds."
        return result
    except Exception as exc:
        result["message"] = f"mkdir failed ({type(exc).__name__}: {exc})."
        return result

    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        result["message"] = detail or "Could not create remote folder."
        return result

    resolved_path = (process.stdout or "").strip().splitlines()
    result["success"] = True
    result["path"] = resolved_path[-1] if resolved_path else target_path
    return result
