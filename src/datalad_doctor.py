"""Checks that a machine can use DataLad with a PRISM project and reach its server.

Backs `prism_tools.py datalad doctor` and the Studio DataLad preflight.
Pure functions; `which`/`run` are injectable so tests never touch the network.
"""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from src.ssh_safety import ssh_target_ok

_DOCS = "https://handbook.datalad.org/en/latest/intro/installation.html"
_GIT_WINDOWS = "https://git-scm.com/download/win"


def install_command(platform: Optional[str] = None, which: Callable[[str], Optional[str]] = shutil.which) -> str:
    """Shell command that installs DataLad + git-annex (git-annex's own commands go on PATH too).

    Windows without uv (the user declined it in install.cmd) falls back to pip.
    """
    if (platform or sys.platform).startswith("win") and not which("uv"):
        return "py -m pip install datalad git-annex"
    return "uv tool install datalad --with-executables-from git-annex"


def install_hint(platform: Optional[str] = None, which: Callable[[str], Optional[str]] = shutil.which) -> str:
    """One sentence for error messages (callers append '. Learn more: ...')."""
    if (platform or sys.platform).startswith("win"):
        return (
            f"Install Git for Windows ({_GIT_WINDOWS}), then run: {install_command('win32', which)} "
            "and restart PRISM Studio"
        )
    cmd = install_command(platform, which)
    note = " (if uv says 'unexpected argument', run 'uv self update' first)" if cmd.startswith("uv ") else ""
    return f"Install with: {cmd}{note}"


def git_install_hint(platform: Optional[str] = None) -> str:
    """How to install git on this OS, in words a non-programmer can follow."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        return f"Download and run the Git for Windows installer: {_GIT_WINDOWS} (keep the defaults), then restart PRISM Studio."
    if platform == "darwin":
        return "Open the Terminal app and run: xcode-select --install   (a window opens; click Install), then restart PRISM Studio."
    return "Open a terminal and run: sudo apt install git   (Fedora: sudo dnf install git), then restart PRISM Studio."


_IDENTITY_FIX = (
    "Git signs every saved change with your name and email. Open a terminal "
    "(Windows: Git Bash or PowerShell) and run:\n"
    'git config --global user.name "Your Name"\n'
    'git config --global user.email "you@example.org"'
)


def get_git_identity(cwd=None) -> dict:
    """The name and email git would sign a saved change with (the person's git config)."""
    values = {}
    for key in ("name", "email"):
        proc = subprocess.run(["git", "config", "--get", f"user.{key}"], capture_output=True, text=True, cwd=cwd)
        values[key] = proc.stdout.strip() if proc.returncode == 0 else ""
    return values


def missing_identity_message(cwd=None) -> str:
    """Empty when DataLad may sign saved changes here, else what to do (before its first commit fails on it)."""
    if all(get_git_identity(cwd).values()):
        return ""
    return (
        "Git does not know your name and email, so DataLad cannot save. "
        "Enter them on the Settings page (Settings > DataLad Version Control), or run: "
        'prism_tools.py datalad identity --name "Your Name" --email you@example.org'
    )


def datalad_preflight(project, *, which: Callable[[str], Optional[str]] = shutil.which, validate: bool = False) -> list:
    """Everything that would make DataLad fail on this project, as plain sentences (empty list = ready).

    Runs before DataLad touches the project; reports all problems at once, each with its fix.
    validate=True also requires an untracked project that already has subjects to validate: the save gate refuses
    every later save of an invalid one, so DataLad would leave it unsavable.
    """
    project = Path(project)
    problems = []
    for tool in ("git", "git-annex", "datalad"):
        if not which(tool):
            problems.append(f"{tool} is not installed. {_tool_fix(tool, which)}")
    if not which("git"):
        return problems
    cwd = project if project.is_dir() else None
    if cwd:
        from src.project_settings import adopt_legacy_project_identity

        adopt_legacy_project_identity(project)
    identity_problem = missing_identity_message(cwd)
    if identity_problem:
        problems.append(identity_problem)
    if cwd is None or not os.access(project, os.W_OK | os.X_OK):
        problems.append(f"PRISM cannot write to {project}. Check that the folder exists and that you own it.")
        return problems

    if validate and not (project / ".datalad").exists() and any(project.glob("sub-*")):
        from src.share_publish import validate_for_publish

        try:
            errors = validate_for_publish(project)
        except (Exception, SystemExit) as exc:  # fail closed, like the gate
            errors = [f"Validation could not run: {exc}"]
        if errors:
            problems.append(
                "The project does not validate yet, and PRISM's save gate refuses to save a project that does not. "
                "Fix this first, then enable DataLad:\n- " + "\n- ".join(errors)
            )

    top = subprocess.run(["git", "-C", str(project), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode == 0:
        if Path(top.stdout.strip()).resolve() != project.resolve():
            problems.append(
                f"This folder is inside another git repository ({top.stdout.strip()}). "
                "Move the project out of it, or DataLad would nest inside it."
            )
    elif "dubious ownership" in top.stderr:
        problems.append(
            "Git refuses this folder because it belongs to another user. Run:\n"
            f'git config --global --add safe.directory "{project}"'
        )

    if not identity_problem:  # a real commit catches broken hooks / git config that reading the config cannot
        with tempfile.TemporaryDirectory() as tmp:
            for cmd in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "prism preflight"]):
                proc = subprocess.run(["git", "-C", tmp, *cmd], capture_output=True, text=True)
                if proc.returncode != 0:
                    problems.append(f"Git could not make a test commit: {(proc.stderr or proc.stdout).strip()}")
                    break
    return problems


def check_git_identity(name: str, email: str) -> tuple:
    """(name, email) trimmed, or ValueError with the sentence to show."""
    name, email = (name or "").strip(), (email or "").strip()
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or "\n" in name:
        raise ValueError("Enter your name and a valid email address (like you@example.org).")
    return name, email


def set_git_identity(name: str, email: str) -> dict:
    """Write user.name and user.email to the global git config (`datalad identity` without a project)."""
    name, email = check_git_identity(name, email)
    for key, value in (("user.name", name), ("user.email", email)):
        proc = subprocess.run(["git", "config", "--global", key, value], capture_output=True, text=True)
        if proc.returncode != 0:
            raise ValueError(f"git could not save {key}: {proc.stderr.strip()}")
    return {"name": name, "email": email}


def _check_git_identity(git_path: str, run: Run) -> dict:
    values = {}
    for key in ("user.name", "user.email"):
        code, out = run([git_path, "config", "--global", key])
        values[key] = out.strip() if code == 0 else ""
    if all(values.values()):
        return _result("git-identity", True, f"{values['user.name']} <{values['user.email']}>")
    return _result("git-identity", False, "Git does not know your name and email yet.", _IDENTITY_FIX)


def _tool_fix(tool: str, which: Callable[[str], Optional[str]] = shutil.which) -> str:
    if tool == "git":
        return git_install_hint()
    if tool == "ssh":
        return "Install/enable the OpenSSH client (Windows: Settings > Optional features > OpenSSH Client)"
    return f"{install_hint(which=which)}. See {_DOCS}"  # git-annex, datalad
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
            return ssh_dir / name, pub.read_text(encoding="utf-8").strip() if pub.is_file() else ""
    return None, ""


def _check_server(url: str, ssh_path: Optional[str], pubkey: str, run: Run) -> dict:
    target = parse_ssh_target(url)
    if target is None:
        return _result("server", True, "Local or non-SSH location; no SSH login needed.")
    if not ssh_path:
        return _result("server", False, "No SSH client.", _tool_fix("ssh"))
    user, host, port = target
    login = f"{user}@{host}" if user else host
    if not ssh_target_ok(login):
        return _result("server", False, "Invalid server host.", "Check the server URL.")
    # accept-new trusts an unseen host on first contact (same as answering "yes" to
    # ssh's prompt) but still refuses a *changed* host key.
    cmd = [ssh_path, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
           "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        cmd += ["-p", str(port)]
    code, output = run(cmd + ["--", login, "true"])
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
            results.append(_result(tool, False, "Not found on PATH.", _tool_fix(tool, which)))
            continue
        _, out = run([path, _VERSION_ARGS[tool]])
        results.append(_result(tool, True, (out.strip().splitlines() or [path])[0]))

    if results[0]["ok"]:  # git found
        results.append(_check_git_identity(which("git") or "git", run))

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
