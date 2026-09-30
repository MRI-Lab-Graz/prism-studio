"""Checks that a machine can use DataLad with a PRISM project and reach its server.

Backs `prism_tools.py datalad doctor` and the Studio DataLad preflight.
Pure functions; `which`/`run` are injectable so tests never touch the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

_DOCS = "https://handbook.datalad.org/en/latest/intro/installation.html"
_TOOL_FIX = {
    "git": "Install Git: https://git-scm.com/downloads",
    "git-annex": f"Install git-annex (Windows: use the installer). See {_DOCS}",
    "datalad": "Install with: uv tool install datalad git-annex  (or see " + _DOCS + ")",
    "ssh": "Install/enable the OpenSSH client (Windows: Settings > Optional features > OpenSSH Client)",
}
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
    if "permission denied" in low:
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
        return _result("server", False, "No SSH client.", _TOOL_FIX["ssh"])
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
            else " You have no key yet: run `prism datalad keygen`, then send the public key to the admin."
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
            results.append(_result(tool, False, "Not found on PATH.", _TOOL_FIX[tool]))
            continue
        _, out = run([path, _VERSION_ARGS[tool]])
        results.append(_result(tool, True, (out.strip().splitlines() or [path])[0]))

    key_path, pubkey = _find_key(ssh_dir)
    if key_path:
        results.append(_result("ssh-key", True, str(key_path)))
    else:
        results.append(
            _result("ssh-key", False, f"No SSH key in {ssh_dir}.",
                    "Run `prism datalad keygen`, then send the printed public key to the server admin.")
        )
    if url:
        results.append(_check_server(url, which("ssh"), pubkey, run))
    return results


def generate_key(
    ssh_dir: Optional[Path] = None,
    *,
    which: Callable[[str], Optional[str]] = shutil.which,
    run: Run = _default_run,
) -> str:
    """Create ~/.ssh/id_ed25519 (never overwriting) and return the public key to send to the admin."""
    ssh_dir = Path(ssh_dir) if ssh_dir else Path.home() / ".ssh"
    key = ssh_dir / "id_ed25519"
    if key.exists():
        raise FileExistsError(f"{key} already exists; not overwriting it.")
    keygen = which("ssh-keygen")
    if not keygen:
        raise RuntimeError(_TOOL_FIX["ssh"])
    ssh_dir.mkdir(parents=True, exist_ok=True)
    # ponytail: empty passphrase so BatchMode logins work without an ssh-agent; add a --passphrase option if admins require one.
    code, output = run([keygen, "-t", "ed25519", "-N", "", "-C", "prism-studio", "-f", str(key)])
    if code != 0:
        raise RuntimeError(output.strip() or "ssh-keygen failed")
    return Path(f"{key}.pub").read_text().strip()
