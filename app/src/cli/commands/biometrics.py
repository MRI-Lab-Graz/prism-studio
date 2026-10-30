"""Biometrics-related prism_tools command handlers."""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

from src.converters.excel_to_biometrics import process_excel_biometrics
from src.library_validator import check_uniqueness
from src.utils.io import ensure_dir as _ensure_dir

_APP_ROOT = Path(__file__).resolve().parents[3]


def cmd_biometrics_detect(args) -> None:
    """Handle 'biometrics detect' command."""
    from src.converters.biometrics import (
        detect_biometrics_in_table,
    )  # lazy: uses canonical shim

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
    """Handle 'biometrics convert': what Studio's Convert does, including saving into the project."""
    import tempfile

    from src.conversion_to_project import plan_template_copies, save_conversion_to_project
    from src.converters.biometrics import (
        convert_biometrics_table_to_prism_dataset,
    )  # lazy
    from src.subject_id_matching import load_existing_participant_ids
    from src.survey_library_resolution import resolve_survey_library

    input_path = Path(args.input)
    output_root = Path(args.output).resolve()

    project_path: Path | None = None
    if getattr(args, "project", None):
        given = Path(args.project).resolve()
        project_path = given.parent if given.is_file() else given
    elif (output_root / "project.json").is_file():
        project_path = output_root  # writing into a PRISM project: its templates and participants apply

    if getattr(args, "library_dir", None):
        library_dir = Path(args.library_dir)
    else:
        try:
            library_root = resolve_survey_library(project_path, _APP_ROOT.parent)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        library_dir = library_root / "biometrics" if (library_root / "biometrics").is_dir() else library_root
    if not list(library_dir.glob("biometrics-*.json")):
        print(f"Error: No biometrics templates found in: {library_dir}", file=sys.stderr)
        sys.exit(1)

    sheet = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    tasks_to_export: list[str] | None = None
    raw_tasks = str(getattr(args, "tasks", "") or "").strip()
    if raw_tasks:
        tasks_to_export = [t.strip() for t in raw_tasks.split(",") if t.strip()]

    dry_run = bool(getattr(args, "dry_run", False))
    # Into a project: convert into a staging folder, then save it into the project as Studio does.
    stage = project_path is not None and output_root == project_path
    staging = tempfile.TemporaryDirectory(prefix="prism_biometrics_convert_") if (stage or dry_run) else None
    convert_into = Path(staging.name) / "rawdata" if staging else output_root
    force = getattr(args, "force", None)
    if force is None:
        force = project_path is not None

    try:
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_path,
            library_dir=library_dir,
            output_root=convert_into,
            id_column=getattr(args, "id_column", None) or None,
            session_column=getattr(args, "session_column", None) or None,
            session=getattr(args, "session", None) or None,
            sheet=sheet,
            unknown=getattr(args, "unknown", "warn"),
            force=bool(force),
            name=getattr(args, "name", None) or None,
            tasks_to_export=tasks_to_export,
            existing_participant_ids=load_existing_participant_ids(project_path) if project_path else set(),
        )
        if stage and not dry_run:
            save_conversion_to_project(
                project_root=project_path,
                staged_root=convert_into,
                convert_result=result,
                source_path=input_path,
                source_name=input_path.name,
                session_override=getattr(args, "session", None),
                template_version_overrides=None,
                modality="biometrics",
                run_message="PRISM: Copy converted biometrics files into project",
                conv_type="biometrics",
                extra_pairs=plan_template_copies("biometrics", library_dir, result.tasks_included, project_path),
                log_fn=lambda message, level="info": print(message) if message else None,
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if staging is not None:
            staging.cleanup()

    if dry_run:
        print(f"Dry run: converted {input_path.name}, nothing written to {output_root}")
    else:
        print(f"Converted {input_path.name} -> {output_root}")
    if result.tasks_included:
        print(f"Tasks: {', '.join(result.tasks_included)}")
    if result.unknown_columns:
        for col in result.unknown_columns:
            print(f"Warning: unknown column ignored: {col}", file=sys.stderr)
    for note in result.notes:
        print(f"Warning: {note}", file=sys.stderr)


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
