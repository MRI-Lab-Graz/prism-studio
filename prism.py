#!/usr/bin/env python3
import os
import sys

# Redirect to the consolidated app folder
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_script = os.path.join(current_dir, "app", "prism.py")
    if os.path.exists(app_script):
        os.execv(sys.executable, [sys.executable, app_script] + sys.argv[1:])
    else:
        print(f"Error: {app_script} not found.")
        sys.exit(1)
