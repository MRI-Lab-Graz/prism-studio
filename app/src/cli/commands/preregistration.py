"""Preregistration prism_tools command handlers (thin adapters over src.preregistration)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.preregistration import load_draft


def cmd_preregistration_draft(args) -> None:
    try:
        markdown = load_draft(args.project)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(f"Wrote preregistration draft to {args.output}")
    else:
        print(markdown)
