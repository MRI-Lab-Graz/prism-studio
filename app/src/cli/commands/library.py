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
        sys.exit(1)

    p = Path(args.path)
    if p.is_file():
        process_file(p, schema)
    elif p.is_dir():
        for f in p.glob("*.json"):
            process_file(f, schema)
    else:
        print(f"Error: Path not found: {args.path}")
        sys.exit(1)


_APP_ROOT_FOR_SCHEMAS = Path(__file__).resolve().parents[3]


def cmd_library_template_check(args) -> None:
    """List what a project's survey templates still lack to be converted with - the check Studio runs before a
    conversion: the same function runs both."""
    from src.survey_template_check import project_template_warnings, validate_project_templates_for_tasks

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()] if args.tasks else None
    issues = validate_project_templates_for_tasks(
        tasks=tasks, project_path=str(Path(args.project).resolve()), schema_version=args.schema_version
    )
    for issue in issues:
        print(issue["message"])
    for warning in project_template_warnings(tasks=tasks, project_path=str(Path(args.project).resolve())):
        print(f"Warning: {warning['file']}: {warning['message']}")
    if issues:
        sys.exit(1)
    print("All survey templates are complete.")


def cmd_library_template_score(args) -> None:
    """How complete a template is: the numbers the template editor's rings show (the same function runs both).
    Exit 1 when it cannot be used yet (a required field is empty); recommended fields never decide that."""
    from src.template_completeness import template_completeness

    template_path = Path(args.template).resolve()
    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: --template could not be read: {exc}")
        sys.exit(1)
    result = template_completeness(
        template,
        source=template_path.name,
        app_root=_APP_ROOT_FOR_SCHEMAS,
        schema_version=args.schema_version,
        project=not args.is_global,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for label, key in (("Required", "required"), ("Recommended", "recommended")):
            part = result[key]
            print(f"{label}: {part['filled']}/{part['total']} ({result['percent'][key]}%)")
            for path in part["missing"]:
                print(f"  - {path}")
        for problem in result["problems"]:
            print(f"Problem: {problem}")
    if not result["complete"]:
        sys.exit(1)


def cmd_library_template_save(args) -> None:
    """Validate and save a single template into a project's library (or your personal one) -
    the CLI equivalent of the Studio GUI's Template Editor Save action: the same function runs both."""
    from src.template_save import TemplateExists, TemplateInvalid, save_template

    template_path = Path(args.template).resolve()
    if not template_path.exists():
        print(f"Error: --template not found: {template_path}")
        sys.exit(1)
    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: --template is not valid JSON: {exc}")
        sys.exit(1)

    to_personal = getattr(args, "to", "project") == "personal"
    if not to_personal and not args.project:
        print("Error: --project is required (or use --to personal)")
        sys.exit(1)
    try:
        saved = save_template(
            args.modality,
            args.filename,
            template,
            target="personal" if to_personal else "project",
            project_root=Path(args.project).resolve() if args.project else None,
            app_root=_APP_ROOT_FOR_SCHEMAS,
            schema_version=args.schema_version,
            relaxed=bool(args.is_global),
            allow_overwrite=bool(args.force),
        )
    except TemplateInvalid as exc:
        print("Error: template validation failed:")
        for err in exc.errors:
            print(f"  - {err['path']}: {err['message']}")
        sys.exit(1)
    except TemplateExists as exc:
        print(f'Error: "{exc.path.name}" already exists in the {"personal" if to_personal else "project"} library. Pass --force to overwrite.')
        sys.exit(1)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    for field in saved.missing:
        print(f"warning: {field['message']}")
    if saved.removed:
        print(f"removed LimeSurvey export settings from {len(saved.removed)} items")
    print(f"✅ Saved to {saved.path}")


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


def cmd_library_share_template(args) -> None:
    """Print the prefilled share mail for a template file - the CLI equivalent of
    the Studio Template Editor's share offer after saving a new template."""
    from src.template_share import share_mail

    path = Path(args.input)
    mail = share_mail(json.loads(path.read_text(encoding="utf-8")), path.name)
    print(f"To:      {mail['to']}")
    print(f"Subject: {mail['subject']}")
    print(f"\n{mail['body']}\n")
    print(f"Mail link: {mail['mailto']}")
    print(f"Attach {path} and send it.")


def cmd_library_check_path(args) -> None:
    """Check a folder is a usable global template library (or recipes folder with
    --recipes) - the same check the Studio settings page runs before saving."""
    from src.config import library_folder_error, recipes_folder_error

    check = recipes_folder_error if args.recipes else library_folder_error
    problem = check(args.path)
    if problem:
        print(f"❌ {problem}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ {args.path} is valid")
