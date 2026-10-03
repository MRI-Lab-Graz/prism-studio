"""Checks that a machine can use DataLad with a PRISM project and reach its server.

Backs `prism_tools.py datalad doctor` and the Studio DataLad preflight.
Pure functions; `which`/`run` are injectable so tests never touch the network.
"""

from __future__ import annotations

import functools
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

_DOCS = "https://handbook.datalad.org/en/latest/intro/installation.html"
_GIT_WINDOWS = "https://git-scm.com/download/win"


def install_command(platform: Optional[str] = None) -> str:
    """Shell command that installs DataLad + git-annex. Windows has Python but not uv."""
    if (platform or sys.platform).startswith("win"):
        return "py -m pip install datalad git-annex"
    return "uv tool install datalad git-annex"


def install_hint(platform: Optional[str] = None) -> str:
    """One sentence for error messages (callers append '. Learn more: ...')."""
    if (platform or sys.platform).startswith("win"):
        return (
            f"Install Git for Windows ({_GIT_WINDOWS}), then run: {install_command('win32')} "
            "and restart PRISM Studio"
        )
    return f"Install with: {install_command(platform)}"


def _tool_fix(tool: str) -> str:
    if tool == "git":
        return f"Install Git: {_GIT_WINDOWS if sys.platform.startswith('win') else 'https://git-scm.com/downloads'}"
    if tool == "ssh":
        return "Install/enable the OpenSSH client (Windows: Settings > Optional features > OpenSSH Client)"
    return f"{install_hint()}. See {_DOCS}"  # git-annex, datalad
_VERSION_ARGS = {"git": "--version", "git-annex": "version", "datalad": "--version", "ssh": "-V"}
_KEY_NAMES = ("id_ed25519", "id_ecdsa", "id_rsa")
_SCP_LIKE = re.compile(r"^([^@/\s:]+)@([^:/\s]+):(?!//)")

Run = Callable[[list], tuple]


def parse_ssh_target(url: str) -> Optional[tuple]:
    """(user, host, port) for ssh-style URLs, else None (local path, https, ...)."""
    url = (url or "").strip()
    if url.startswith("ria+"):
        url = url[4:]
    if url.startswith("ssh://"):
        parsed = urlparse(url)
        if parsed.hostname:
            return parsed.username, parsed.hostname, parsed.port
        return None
    match = _SCP_LIKE.match(url)
    if match:
        return match.group(1), match.group(2), None
    return None


def classify_ssh_error(stderr: str) -> tuple:
    """(code, plain-language message) for the common ways an SSH login fails."""
    low = (stderr or "").lower()
    if "permission denied (" in low:  # ssh's "(publickey,...)"; a bare local "Permission denied" is not a key problem
        return "key_rejected", "The server did not accept your SSH key."
    if "host key verification failed" in low or "remote host identification has changed" in low:
        return "host_key", (
            "The server's host key is unknown or has changed. Ask your admin to confirm it, "
            "then remove the old entry with: ssh-keygen -R <host>"
        )
    if any(s in low for s in ("could not resolve", "timed out", "connection refused", "no route")):
        return "unreachable", "Cannot reach the server. Check the URL and your VPN/campus network."
    return "unknown", (stderr or "").strip() or "SSH connection failed."


def _default_run(cmd: list) -> tuple:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 255, "Connection timed out"
    except OSError as exc:
        return 255, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _result(name: str, ok: bool, detail: str = "", fix: str = "") -> dict:
    return {"name": name, "ok": ok, "detail": detail, "fix": fix}


def _find_key(ssh_dir: Path) -> tuple:
    for name in _KEY_NAMES:
        if (ssh_dir / name).is_file():
            pub = ssh_dir / f"{name}.pub"
            return ssh_dir / name, pub.read_text().strip() if pub.is_file() else ""
    return None, ""


def _check_server(url: str, ssh_path: Optional[str], pubkey: str, run: Run) -> dict:
    target = parse_ssh_target(url)
    if target is None:
        return _result("server", True, "Local or non-SSH location; no SSH login needed.")
    if not ssh_path:
        return _result("server", False, "No SSH client.", _tool_fix("ssh"))
    user, host, port = target
    login = f"{user}@{host}" if user else host
    # accept-new trusts an unseen host on first contact (same as answering "yes" to
    # ssh's prompt) but still refuses a *changed* host key.
    cmd = [ssh_path, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
           "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        cmd += ["-p", str(port)]
    code, output = run(cmd + [login, "true"])
    if code == 0:
        return _result("server", True, f"Logged in to {login} with your SSH key.")
    kind, message = classify_ssh_error(output)
    fix = message
    if kind == "key_rejected":
        fix += (
            f" Send this public key to the server admin:\n{pubkey}"
            if pubkey
            else " You have no SSH key yet: ask your IT admin to set one up for you."
        )
    return _result("server", False, output.strip(), fix)


def run_doctor(
    url: Optional[str] = None,
    *,
    which: Callable[[str], Optional[str]] = shutil.which,
    run: Run = _default_run,
    ssh_dir: Optional[Path] = None,
) -> list:
    ssh_dir = Path(ssh_dir) if ssh_dir else Path.home() / ".ssh"
    results = []
    for tool in ("git", "git-annex", "datalad", "ssh"):
        path = which(tool)
        if not path:
            results.append(_result(tool, False, "Not found on PATH.", _tool_fix(tool)))
            continue
        _, out = run([path, _VERSION_ARGS[tool]])
        results.append(_result(tool, True, (out.strip().splitlines() or [path])[0]))

    key_path, pubkey = _find_key(ssh_dir)
    if key_path:
        results.append(_result("ssh-key", True, str(key_path)))
    else:
        results.append(
            _result("ssh-key", False, f"No SSH key in {ssh_dir}.",
                    "Ask your IT admin to set up an SSH key for you and register it on the server.")
        )
    if url:
        results.append(_check_server(url, which("ssh"), pubkey, run))
    return results



def explain_failure(message: str) -> str:
    """Prefix a failed push/sync message with a plain-language SSH explanation, keeping the original text."""
    kind, plain = classify_ssh_error(message)
    if kind == "unknown":
        return message
    return (
        f"{plain} Use \"Check this computer\" (or `prism_tools.py datalad doctor`) to see what to fix."
        f"\n\nDetails: {message}"
    )


def explain_ssh_failures(fn):
    """Decorator for ProjectManager push operations returning {"success", "message", ...}."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if isinstance(result, dict) and not result.get("success") and result.get("message"):
            result["message"] = explain_failure(str(result["message"]))
        return result

    return wrapper
