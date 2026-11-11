"""Biosample prism_tools command handlers."""

from __future__ import annotations

import sys
from pathlib import Path


def cmd_biosample_template(args) -> None:
    """Handle 'biosample template': write the Excel template."""
    from src.biosample_template import write_biosample_template

    write_biosample_template(Path(args.output))
    print(f"Wrote {args.output}")


def cmd_biosample_import(args) -> None:
    """Handle 'biosample import': write biosample files into the project."""
    from src.biosample_import import import_biosample

    res = import_biosample(
        Path(args.input), Path(args.project), args.specimen, args.overwrite, args.dry_run
    )
    for message in res.warnings:
        print(f"Warning: {message}")
    for name in res.written:
        print(f"{'would write ' if args.dry_run else ''}{name}")
    for message in res.errors:
        print(f"Error: {message}", file=sys.stderr)
    if res.errors:
        sys.exit(1)
