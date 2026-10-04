#!/usr/bin/env python3
"""Re-exec helper shared by the root launcher scripts.

On Windows ``os.execv`` hands argv to the C runtime, which joins the
arguments with plain spaces and does no quoting.  Any path containing a
space (e.g. ``C:\\Users\\x\\Downloads\\prism-studio-main (1)\\...``) is
therefore split apart and the child interpreter gets garbage.  Use
``subprocess`` there, which quotes properly, and keep ``execv`` on POSIX
where it is exact and cheaper.
"""

import os
import subprocess
import sys
from pathlib import Path


def exec_python(executable, args):
    """Run ``executable`` with ``args`` (argv[1:]), replacing this process."""
    cmd = [str(executable)] + [str(a) for a in args]
    if sys.platform == "win32":
        sys.exit(subprocess.run(cmd).returncode)
    os.execv(cmd[0], cmd)


def find_project_root(script_file):
    """Project root for a launcher: its folder, or two up when run from .venv/bin."""
    current = Path(script_file).resolve().parent
    if current.name == "bin" and current.parent.name == ".venv":
        return current.parent.parent
    return current


def ensure_venv(project_root, strict):
    """Re-exec the running script under ``<project_root>/.venv`` if not already in it.

    strict: a missing venv exits (prism-studio). Otherwise it only warns and
    carries on, and CI skips the check entirely (prism, prism_tools).
    """
    if os.environ.get("PRISM_SKIP_VENV_CHECK"):
        return
    if not strict and os.environ.get("CI"):
        return

    venv_dir = project_root / ".venv"
    if not venv_dir.exists():
        if strict:
            print(f"Error: Virtual environment not found at {venv_dir}")
            print("Please run 'bash install.sh' or 'install.cmd' to create it.")
            sys.exit(2)
        print(f"Warning: Virtual environment not found at {venv_dir}")
        print("Run install.sh or install.cmd to create it.")
        return

    sub = ("Scripts", "python.exe") if sys.platform == "win32" else ("bin", "python")
    venv_python = venv_dir.joinpath(*sub)
    if not venv_python.exists():
        if strict:
            print(f"Error: Virtual environment Python not found at {venv_python}")
            print("Please run 'bash install.sh' to recreate the virtual environment.")
            sys.exit(3)
        print(f"Warning: Virtual environment Python not found at {venv_python}")
        return

    if sys.executable == str(venv_python) or sys.prefix == str(venv_dir):
        return

    print(f"⚠️  Activating virtual environment: {venv_dir}")
    try:
        exec_python(venv_python, sys.argv)
    except OSError as e:
        print(f"Error: Failed to exec into virtualenv python: {e}")
        sys.exit(4)
