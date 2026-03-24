from __future__ import annotations

import shlex
import subprocess
from typing import Mapping, Sequence


def build_dedicated_terminal_relaunch_args(argv_tail: Sequence[str]) -> list[str]:
    """Return relaunch args and guarantee recursion guard flag is present once."""
    relaunch_args = list(argv_tail)
    if "--no-dedicated-terminal" not in relaunch_args:
        relaunch_args.append("--no-dedicated-terminal")
    return relaunch_args


def build_unix_dedicated_terminal_command(
    *,
    executable: str,
    argv_tail: Sequence[str],
    attached_env_name: str,
) -> str:
    """Build a shell command used by macOS/Linux terminal launchers."""
    argv = [executable, *build_dedicated_terminal_relaunch_args(argv_tail)]
    quoted = " ".join(shlex.quote(part) for part in argv)
    return f"export {attached_env_name}=1; {quoted}"


def build_windows_dedicated_terminal_command(
    *,
    executable: str,
    argv_tail: Sequence[str],
    attached_env_name: str,
) -> str:
    """Build a Windows cmd-safe relaunch command with explicit env handoff."""
    launch_args = subprocess.list2cmdline(
        [executable, *build_dedicated_terminal_relaunch_args(argv_tail)]
    )
    return f'set "{attached_env_name}=1" && {launch_args}'


def should_relaunch_in_dedicated_terminal(
    *,
    frozen: bool,
    platform: str,
    no_dedicated_terminal: bool,
    env: Mapping[str, str],
    show_dedicated_terminal: bool,
    attached_env_name: str,
    disabled_env_name: str,
    force_env_name: str,
) -> bool:
    """Return whether runtime should relaunch app in a dedicated terminal."""
    if not frozen:
        return False
    if no_dedicated_terminal:
        return False
    if env.get(disabled_env_name) == "1":
        return False
    if env.get(attached_env_name) == "1":
        return False
    if platform.startswith("win"):
        if env.get(force_env_name) == "1":
            return True
        return show_dedicated_terminal
    return show_dedicated_terminal
