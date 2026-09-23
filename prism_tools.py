#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from launcher_exec import exec_python  # noqa: E402

# Redirect to the consolidated app folder
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_script = os.path.join(current_dir, "app", "prism_tools.py")
    if os.path.exists(app_script):
        exec_python(sys.executable, [app_script] + sys.argv[1:])
    else:
        print(f"Error: {app_script} not found.")
        sys.exit(1)
