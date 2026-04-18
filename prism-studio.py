#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def find_project_root():
    """Find the project root directory (contains app/ and .venv/)."""
    # Start from script location
    current = Path(__file__).resolve().parent

    # If we're in .venv/bin/, go up two levels
    if current.name == "bin" and current.parent.name == ".venv":
        return current.parent.parent

    # Otherwise, current directory should be the project root
    return current


# Check if we're in the correct virtual environment
def check_and_activate_venv():
    """Check if the correct venv is activated, if not try to re-execute with it."""
    # Skip check only when explicitly requested by a verification harness.
    if os.environ.get("PRISM_SKIP_VENV_CHECK"):
        return

    project_root = find_project_root()
    venv_dir = project_root / ".venv"

    # Check if venv exists
    if not venv_dir.exists():
        print(f"Error: Virtual environment not found at {venv_dir}")
        print("Please run 'bash setup.sh' or 'setup.ps1' to create it.")
        sys.exit(2)

    # Determine venv python path
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    # Check if venv python exists
    if not venv_python.exists():
        print(f"Error: Virtual environment Python not found at {venv_python}")
        print("Please run 'bash setup.sh' to recreate the virtual environment.")
        sys.exit(3)

    # Strict mode: reject symlinked interpreters to avoid external runtimes.
    if venv_python.is_symlink():
        resolved = venv_python.resolve()
        print(
            "Error: Virtual environment Python must be a local binary, "
            f"but {venv_python} points to {resolved}."
        )
        print("Please run 'bash setup.sh' to recreate a strict local virtual environment.")
        sys.exit(5)

    # Check if we're already running from the venv.
    try:
        if sys.executable == str(venv_python) or sys.prefix == str(venv_dir):
            return
    except Exception:
        # Defensive: continue to activation logic if sys checks fail.
        pass

    # Re-execute with venv python
    print(f"⚠️  Activating virtual environment: {venv_dir}")
    try:
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    except OSError as e:
        print(f"Error: Failed to exec into virtualenv python: {e}")
        sys.exit(4)


# Check venv before doing anything else
check_and_activate_venv()

# Redirect to the consolidated app folder
if __name__ == "__main__":
    project_root = find_project_root()
    app_script = project_root / "app" / "prism-studio.py"
    if app_script.exists():
        os.execv(sys.executable, [sys.executable, str(app_script)] + sys.argv[1:])
    else:
        print(f"Error: {app_script} not found.")
        sys.exit(1)
