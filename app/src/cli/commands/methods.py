"""Methods prism_tools command handlers (thin adapters over src.methods_project)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.methods_project import build_methods
from src.text_export import convert


def emit_document(markdown: str, fmt: str, output: str | None) -> None:
    """Convert Markdown to ``fmt`` and print or write it; exit 2 on a user error."""
    if fmt == "docx" and not output:
        print("Error: --format docx is binary and needs --output FILE")
        sys.exit(2)
    try:
        data = convert(markdown, fmt)
    except RuntimeError as exc:  # python-docx missing
        print(f"Error: {exc}")
        sys.exit(2)
    if output:
        Path(output).write_bytes(data)
        print(f"Wrote {fmt} to {output}")
    else:
        print(data.decode("utf-8"))


def cmd_methods_generate(args) -> None:
    try:
        result = build_methods(
            Path(args.project), lang=args.lang, detail_level=args.detail
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(2)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    emit_document(result.md, args.format, args.output)
