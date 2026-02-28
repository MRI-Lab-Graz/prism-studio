#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def _check_venv() -> None:
    # Skip check if explicitly requested or in CI environment
    if os.environ.get("PRISM_SKIP_VENV_CHECK") or os.environ.get("CI"):
        return

    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_path = os.path.join(os.path.dirname(current_dir), ".venv")
    if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
        print("❌ Error: You are not running inside the prism virtual environment!")
        print("   Please activate the venv first:")
        if os.name == "nt":
            print(f"     {venv_path}\\Scripts\\activate")
        else:
            print(f"     source {venv_path}/bin/activate")
        print("   Then run this script again.")
        sys.exit(1)


def main() -> None:
    _check_venv()

    app_root = Path(__file__).resolve().parent
    if str(app_root) not in sys.path:
        sys.path.append(str(app_root))

    from src.cli.entrypoint import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
