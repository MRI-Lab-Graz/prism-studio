"""Biometrics-related prism_tools command handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from src.converters.excel_to_biometrics import process_excel_biometrics
from src.library_validator import check_uniqueness
from src.utils.io import ensure_dir as _ensure_dir


def cmd_biometrics_import_excel(args):
    """Import biometrics templates/library from Excel."""
    print(f"Importing biometrics library from {args.excel} (sheet={args.sheet})...")
    try:
        sheet = (
            int(args.sheet)
            if isinstance(args.sheet, str) and args.sheet.isdigit()
            else args.sheet
        )
        if getattr(args, "library_root", None):
            output_dir = Path(args.library_root) / "biometrics"
        else:
            output_dir = Path(args.output)
            if output_dir.name != "biometrics":
                output_dir = output_dir / "biometrics"

        output_dir_str = str(_ensure_dir(output_dir))
        process_excel_biometrics(
            args.excel,
            output_dir_str,
            sheet_name=sheet,
            equipment=args.equipment,
            supervisor=args.supervisor,
        )

        print("\nValidating imported files...")
        check_uniqueness(output_dir_str)
    except Exception as e:
        print(f"Error importing Excel: {e}")
        sys.exit(1)
