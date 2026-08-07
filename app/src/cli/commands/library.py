"""Library-related prism_tools command handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.prism_template_validation import (
    relax_schema_for_library_template,
    strip_template_editor_internal_keys,
    validate_template_against_schema,
)
from src.reporting import generate_methods_text
from src.survey_template_normalization import normalize_survey_template_for_validation
from src.utils.io import dump_json_text


def cmd_library_generate_methods_text(args) -> None:
    libs = []
    if args.survey_lib:
        libs.append(args.survey_lib)
    if args.biometrics_lib:
        libs.append(args.biometrics_lib)

    generate_methods_text(libs, args.output, lang=args.lang)


def cmd_library_sync(args) -> None:
    """Synchronize keys across library files using a template."""
    from src.maintenance.sync_survey_keys import sync_survey_keys
    from src.maintenance.sync_biometrics_keys import sync_biometrics_keys

    if args.modality == "survey":
        sync_survey_keys(args.path)
    elif args.modality == "biometrics":
        sync_biometrics_keys(args.path)
    else:
        print(f"Error: Unsupported modality for sync: {args.modality}")


def cmd_library_catalog(args) -> None:
    """Generate a CSV catalog of the survey library."""
    from src.maintenance.catalog_survey_library import generate_index

    generate_index(args.input, args.output)


def cmd_library_fill(args) -> None:
    """Fill missing metadata keys in library files based on schema."""
    from src.maintenance.fill_missing_metadata import process_file
    from src.schema_manager import load_schema

    schema = load_schema(args.modality, version=args.version)
    if not schema:
        print(f"Error: Could not load schema for {args.modality}")
        return

    p = Path(args.path)
    if p.is_file():
        process_file(p, schema)
    elif p.is_dir():
        for f in p.glob("*.json"):
            process_file(f, schema)
    else:
        print(f"Error: Path not found: {args.path}")


_APP_ROOT_FOR_SCHEMAS = Path(__file__).resolve().parents[3]


def cmd_library_template_save(args) -> None:
    """Validate and save a single template into a project's library —
    the CLI equivalent of the Studio GUI's Template Editor Save action."""
    from src.schema_manager import load_schema

    filename = str(args.filename).strip()
    if not filename or "/" in filename or "\\" in filename:
        print("Error: --filename must be a bare filename (no path separators)")
        sys.exit(1)
    if not filename.lower().endswith(".json"):
        filename += ".json"

    template_path = Path(args.template).resolve()
    if not template_path.exists():
        print(f"Error: --template not found: {template_path}")
        sys.exit(1)

    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: --template is not valid JSON: {exc}")
        sys.exit(1)
    if not isinstance(template, dict):
        print("Error: --template must be a JSON object")
        sys.exit(1)

    template = strip_template_editor_internal_keys(template)
    if args.modality == "survey":
        template = normalize_survey_template_for_validation(template)

    schema = load_schema(
        args.modality,
        schema_dir=str(_APP_ROOT_FOR_SCHEMAS / "schemas"),
        version=args.schema_version,
    )
    if not schema:
        print(f"Error: Could not load schema for {args.modality}")
        sys.exit(1)
    if args.is_global:
        schema = relax_schema_for_library_template(schema)

    errors = validate_template_against_schema(instance=template, schema=schema)
    if errors:
        print("Error: template validation failed:")
        for err in errors:
            print(f"  - {err['path']}: {err['message']}")
        sys.exit(1)

    project_root = Path(args.project).resolve()
    folder = project_root / "code" / "library" / args.modality
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename

    if target.exists() and not args.force:
        print(
            f'Error: "{filename}" already exists in the project library. '
            "Pass --force to overwrite."
        )
        sys.exit(1)

    target.write_text(dump_json_text(template), encoding="utf-8")
    print(f"✅ Saved to {target}")


def cmd_library_template_delete(args) -> None:
    """Delete a single project-library template — the CLI equivalent of
    the Studio GUI's Template Editor Delete action. Refuses to delete
    outside the project's own code/library/<modality>/ folder (never
    global/official templates)."""
    filename = str(args.filename).strip()
    if not filename or "/" in filename or "\\" in filename:
        print("Error: --filename must be a bare filename (no path separators)")
        sys.exit(1)
    if not filename.lower().endswith(".json"):
        filename += ".json"

    project_root = Path(args.project).resolve()
    project_folder = (project_root / "code" / "library" / args.modality).resolve()
    target = (project_folder / filename).resolve()

    if not str(target).startswith(str(project_folder)):
        print("Error: deletion is only permitted for project-library templates")
        sys.exit(1)

    if not target.exists():
        print(f"Error: template file not found: {target}")
        sys.exit(1)

    if not args.yes:
        confirmation = input(f"Delete {target}? [y/N] ").strip().lower()
        if confirmation not in {"y", "yes"}:
            print("Aborted.")
            return

    target.unlink()
    print(f"✅ Deleted {target}")
