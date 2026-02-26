"""Library-related prism_tools command handlers."""

from __future__ import annotations

from pathlib import Path

from src.reporting import generate_methods_text


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
