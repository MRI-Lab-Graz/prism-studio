"""Preregistration prism_tools command handlers (thin adapters over src.preregistration)."""

from __future__ import annotations

import sys

from src.cli.commands.methods import emit_document
from src.preregistration import load_draft


def cmd_preregistration_draft(args) -> None:
    try:
        markdown = load_draft(args.project)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    emit_document(markdown, args.format, args.output)
