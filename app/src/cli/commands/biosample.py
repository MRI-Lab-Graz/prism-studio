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


def cmd_biosample_migrate_wide(args) -> None:
    """Handle 'biosample migrate-wide': legacy wide sheet -> filled biosample template."""
    from src.biosample_migrate import MigrationError, migrate_wide

    try:
        rep = migrate_wide(
            Path(args.input), Path(args.output), args.panel, args.specimen,
            args.id_column, args.session_column, args.overwrite,
        )
    except MigrationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {args.output}")
    skipped = f", skipped (no values): {', '.join(rep.rows_skipped_empty)}" if rep.rows_skipped_empty else ""
    print(f"Rows read: {rep.rows_read}{skipped}")
    print(f"Data rows written: {rep.data_rows}")
    for title, items in (
        ("Analytes written", rep.analytes_mapped),
        ("Analytes dropped (empty in this file)", rep.analytes_dropped_empty),
        ("Units repaired", rep.unit_repairs),
        ("Assumptions", rep.assumptions),
        ("Warnings", rep.warnings),
    ):
        if items:
            print(f"{title}:")
            for item in items:
                print(f"  {item}")
