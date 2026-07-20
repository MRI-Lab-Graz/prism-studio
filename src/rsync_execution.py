from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

RSYNC_INSTALL_HINT = "Install rsync via your OS package manager (e.g. `brew install rsync`, `apt install rsync`)."

_PROGRESS_PERCENT_RE = re.compile(r"(\d{1,3})%")


def resolve_rsync_executable() -> str:
    return str(shutil.which("rsync") or "").strip()


def is_remote_target(target: str) -> bool:
    """True if `target` looks like a `[user@]host:/path` SSH spec rather than a local path."""
    target = str(target or "")
    if ":" not in target:
        return False
    head = target.split(":", 1)[0]
    if not head or "/" in head or "\\" in head:
        return False
    # A single-character head is a Windows drive letter (e.g. "C:\path"), not a hostname.
    return len(head) > 1


def _split_remote_target(target: str) -> tuple[str, str]:
    host_part, _, remote_path = str(target).partition(":")
    return host_part, remote_path


def ensure_remote_directory(target: str, *, timeout_seconds: int = 30) -> dict[str, Any]:
    """Best-effort `ssh host mkdir -p <path>` so rsync has somewhere to land.

    No-op (success) for local targets, where rsync/the OS handles directory
    creation itself.
    """
    result: dict[str, Any] = {"attempted": False, "success": True, "message": ""}
    if not is_remote_target(target):
        Path(target).mkdir(parents=True, exist_ok=True)
        return result

    ssh_executable = str(shutil.which("ssh") or "").strip()
    if not ssh_executable:
        result["success"] = False
        result["message"] = "ssh executable is not available in this environment."
        return result

    host, remote_path = _split_remote_target(target)
    if not remote_path:
        return result

    command = [ssh_executable, host, "mkdir", "-p", remote_path]
    result["attempted"] = True
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["success"] = False
        result["message"] = f"ssh mkdir timed out after {timeout_seconds} seconds."
        return result
    except Exception as exc:
        result["success"] = False
        result["message"] = f"ssh mkdir failed ({type(exc).__name__}: {exc})."
        return result

    if process.returncode == 0:
        result["success"] = True
        return result

    result["success"] = False
    result["message"] = (process.stderr or process.stdout or "").strip() or "Unknown ssh error."
    return result


def run_rsync_push(
    project_root: Path,
    *,
    remote_target: str,
    rsync_executable: str = "",
    exclude_patterns: list[str] | None = None,
    progress_callback: Any = None,
    is_cancelled: Any = None,
    timeout_seconds: int = 7200,
) -> dict[str, Any]:
    """Copy `project_root`'s contents to `remote_target` with `rsync -a`.

    Additive only (no `--delete`): a destination is treated as a growing
    backup, not a mirror, so files removed locally are left intact remotely.
    """
    root = Path(project_root)
    resolved = str(rsync_executable or resolve_rsync_executable()).strip()
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
            f"rsync executable is not available in this environment. {RSYNC_INSTALL_HINT}"
        )
        return result

    target = str(remote_target or "").strip()
    if not target:
        result["message"] = "No remote target was provided."
        return result

    def _report(percent: int, message: str) -> None:
        if callable(progress_callback):
            progress_callback(percent, message)

    def _cancelled() -> bool:
        return bool(callable(is_cancelled) and is_cancelled())

    dir_result = ensure_remote_directory(target)
    if not dir_result.get("success"):
        result["message"] = f"Could not prepare destination directory: {dir_result.get('message')}"
        return result

    source = str(root).rstrip("/") + "/"
    # `--info=progress2` is GNU-rsync-only; `--progress` (still percentage-per-file)
    # works on both GNU rsync and macOS's bundled openrsync.
    command = [resolved, "-a", "--progress"]
    for pattern in exclude_patterns or []:
        command.extend(["--exclude", pattern])
    command.extend([source, target.rstrip("/") + "/"])

    result["attempted"] = True
    result["command"] = shlex.join(command)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        result["message"] = f"rsync failed to start ({type(exc).__name__}: {exc})."
        return result

    output_lines: list[str] = []
    highest_percent = 10
    try:
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            match = _PROGRESS_PERCENT_RE.search(line)
            if match:
                # rsync's own percent only covers the file currently in
                # flight and resets to 0 for each new file; clamp into a
                # [10, 95] band and never report backwards, so the bar reads
                # as steady progress across the whole transfer instead of
                # sawtoothing between files.
                percent = min(10 + int(int(match.group(1)) * 0.85), 95)
                if percent > highest_percent:
                    highest_percent = percent
                    _report(highest_percent, "Copying files...")
            if _cancelled():
                process.terminate()
                break
        process.wait(timeout=max(1, int(timeout_seconds)))
    except subprocess.TimeoutExpired:
        process.kill()
        result["message"] = f"rsync timed out after {timeout_seconds} seconds."
        result["stdout"] = "".join(output_lines)
        return result
    except Exception as exc:
        result["message"] = f"rsync failed ({type(exc).__name__}: {exc})."
        result["stdout"] = "".join(output_lines)
        return result

    result["stdout"] = "".join(output_lines)

    if _cancelled():
        result["message"] = "Cancelled."
        return result

    if process.returncode == 0:
        result["success"] = True
        result["message"] = "rsync completed."
        return result

    detail = result["stdout"].strip()
    result["message"] = f"rsync failed (exit code {process.returncode}): {detail or 'Unknown rsync error.'}"
    return result


def run_rsync_verify(
    project_root: Path,
    *,
    remote_target: str,
    rsync_executable: str = "",
    exclude_patterns: list[str] | None = None,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Dry-run checksum comparison: confirms the destination matches the source.

    Any line `rsync -avn --checksum` itemizes is a file it would still
    transfer, i.e. a real content/size mismatch (not just a touched mtime).
    """
    root = Path(project_root)
    resolved = str(rsync_executable or resolve_rsync_executable()).strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "verified": False,
        "mismatched_paths": [],
        "message": "",
    }
    if not resolved:
        result["message"] = (
            f"rsync executable is not available in this environment. {RSYNC_INSTALL_HINT}"
        )
        return result

    target = str(remote_target or "").strip()
    if not target:
        result["message"] = "No remote target was provided."
        return result

    source = str(root).rstrip("/") + "/"
    # `-c` (checksum) and `-n` (dry-run) as short flags for compatibility with
    # macOS's bundled openrsync, which lacks the GNU `--checksum` long form.
    command = [resolved, "-acn", "--itemize-changes"]
    for pattern in exclude_patterns or []:
        command.extend(["--exclude", pattern])
    command.extend([source, target.rstrip("/") + "/"])

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["message"] = f"rsync verification timed out after {timeout_seconds} seconds."
        return result
    except Exception as exc:
        result["message"] = f"rsync verification failed ({type(exc).__name__}: {exc})."
        return result

    result["attempted"] = True
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        result["message"] = f"rsync verification failed: {detail or 'Unknown rsync error.'}"
        return result

    mismatched = [
        line.strip()
        for line in (process.stdout or "").splitlines()
        if line.strip() and not line.startswith("sending incremental file list")
    ]
    result["success"] = True
    result["mismatched_paths"] = mismatched
    result["verified"] = not mismatched
    result["message"] = (
        "Destination matches source exactly."
        if result["verified"]
        else f"{len(mismatched)} file(s) differ between source and destination."
    )
    return result
