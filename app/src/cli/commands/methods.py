"""Methods prism_tools command handlers (thin adapters over src.methods_project)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.methods_project import build_methods, render_methods
from src.text_export import emit_document


def cmd_methods_generate(args) -> None:
    try:
        result = build_methods(
            Path(args.project), lang="en", detail_level=args.detail
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    emit_document(result, args.format, args.output, render=render_methods)
