#!/usr/bin/env python3
import os
import sys
from pathlib import Path


# Check if we're in the correct virtual environment
def check_and_activate_venv():
    """Check if the correct venv is activated, if not try to re-execute with it."""
    current_dir = Path(__file__).resolve().parent
    venv_dir = current_dir / ".venv"

    # Check if venv exists
    if not venv_dir.exists():
        print(f"Warning: Virtual environment not found at {venv_dir}")
        print("Run setup.sh or setup.ps1 to create it.")
        return

    # Determine venv python path
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    # Check if we're already running from the venv
    if sys.executable == str(venv_python) or sys.prefix == str(venv_dir):
        return  # Already in venv

    # Check if venv python exists
    if not venv_python.exists():
        print(f"Warning: Virtual environment Python not found at {venv_python}")
        return

    # Re-execute with venv python
    print(f"⚠️  Activating virtual environment: {venv_dir}")
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)


# Check venv before doing anything else
check_and_activate_venv()

# Redirect to the consolidated app folder
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_script = os.path.join(current_dir, "app", "prism-studio.py")
    if os.path.exists(app_script):
        os.execv(sys.executable, [sys.executable, app_script] + sys.argv[1:])
    else:
        print(f"Error: {app_script} not found.")
        sys.exit(1)
