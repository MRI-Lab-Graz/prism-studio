"""Biometrics-related prism_tools command handlers."""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

from src.converters.excel_to_biometrics import process_excel_biometrics
from src.library_validator import check_uniqueness
from src.utils.io import ensure_dir as _ensure_dir


def cmd_biometrics_detect(args) -> None:
    """Handle 'biometrics detect' command."""
    from src.converters.biometrics import detect_biometrics_in_table  # lazy: uses canonical shim

    input_path = Path(args.input)
    library_dir = Path(args.library_dir)

    sheet = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    try:
        tasks = detect_biometrics_in_table(
            input_path=input_path,
            library_dir=library_dir,
            sheet=sheet,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        print(_json.dumps({"tasks": tasks}))
    elif tasks:
        print(f"Detected {len(tasks)} biometric task(s): {', '.join(tasks)}")
    else:
        print("No biometric tasks detected in the input file.")


def cmd_biometrics_convert(args) -> None:
    """Handle 'biometrics convert' command."""
    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset  # lazy

    input_path = Path(args.input)
    library_dir = Path(args.library_dir)
    output_root = Path(args.output)

    sheet = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    tasks_to_export: list[str] | None = None
    raw_tasks = str(getattr(args, "tasks", "") or "").strip()
    if raw_tasks:
        tasks_to_export = [t.strip() for t in raw_tasks.split(",") if t.strip()]

    try:
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_path,
            library_dir=library_dir,
            output_root=output_root,
            id_column=getattr(args, "id_column", None) or None,
            session_column=getattr(args, "session_column", None) or None,
            session=getattr(args, "session", None) or None,
            sheet=sheet,
            unknown=getattr(args, "unknown", "warn"),
            force=getattr(args, "force", False),
            name=getattr(args, "name", None) or None,
            tasks_to_export=tasks_to_export,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Converted {input_path.name} -> {output_root}")
    if result.tasks_included:
        print(f"Tasks: {', '.join(result.tasks_included)}")
    if result.unknown_columns:
        for col in result.unknown_columns:
            print(f"Warning: unknown column ignored: {col}", file=sys.stderr)


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
