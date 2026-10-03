#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from launcher_exec import ensure_venv, exec_python, find_project_root  # noqa: E402

# Check venv before doing anything else
ensure_venv(find_project_root(__file__), strict=False)

# Redirect to the consolidated app folder
if __name__ == "__main__":
    app_script = find_project_root(__file__) / "app" / "prism.py"
    if app_script.exists():
        exec_python(sys.executable, [app_script] + sys.argv[1:])
    else:
        print(f"Error: {app_script} not found.")
        sys.exit(1)
