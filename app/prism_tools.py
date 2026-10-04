#!/usr/bin/env python3
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def main() -> None:
    app_root = Path(__file__).resolve().parent
    if str(app_root) not in sys.path:
        sys.path.append(str(app_root))

    from src.cli.entrypoint import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
