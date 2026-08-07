"""JSON Editor-related prism_tools command handlers.

The Studio GUI's JSON Editor page (app/src/json_editor_blueprint.py) is a
largely self-contained sub-app with its own backend package
(app/src/json_editor/src/backend/), but its "Save to Project" action —
which writes dataset_description.json/participants.json/samples.json/
task-*.json sidecars with real post-save validation — had no CLI
equivalent (audit item P2, docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md).
This reuses the exact same FileManager/JSONValidator/BIDSSchemaLoader
classes the GUI does, via the same sys.path bootstrap the blueprint
itself uses to reach its bundled backend package.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_JSON_EDITOR_SRC = Path(__file__).resolve().parents[2] / "json_editor" / "src"


def _load_json_editor_backend():
    if str(_JSON_EDITOR_SRC) not in sys.path:
        sys.path.insert(0, str(_JSON_EDITOR_SRC))

    from backend.file_manager import FileManager
    from backend.json_validator import JSONValidator
    from schema_loader import BIDSSchemaLoader

    return FileManager, JSONValidator, BIDSSchemaLoader


def cmd_json_editor_save(args) -> None:
    """Save a BIDS sidecar JSON file into a project — the CLI equivalent
    of the Studio GUI's JSON Editor "Save to Project" action. Saves first,
    then validates (matching the GUI's own save-then-validate order);
    validation errors are reported but don't block the save."""
    as_json = bool(getattr(args, "json", False))
    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        print(f"Error: --project is not a directory: {project_root}")
        sys.exit(1)

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"Error: --file not found: {file_path}")
        sys.exit(1)

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: --file is not valid JSON: {exc}")
        sys.exit(1)

    try:
        FileManager, JSONValidator, BIDSSchemaLoader = _load_json_editor_backend()
    except ImportError as exc:
        print(f"Error: JSON editor backend is not available: {exc}")
        sys.exit(1)

    file_manager = FileManager(str(project_root))

    try:
        saved_path = file_manager.save_file(args.type, data)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    validator = JSONValidator()
    schema_loader = BIDSSchemaLoader()
    validation_errors: list[str] = []
    # BIDSSchemaLoader prints load-progress diagnostics that would otherwise
    # pollute --json output; suppress them via its existing opt-out (used
    # the same way by the Studio launcher for the same reason).
    import os

    previous_hide_details = os.environ.get("PRISM_STARTUP_HIDE_DETAILS")
    try:
        if as_json:
            os.environ["PRISM_STARTUP_HIDE_DETAILS"] = "1"
        schema_loader.load_schema()
        schema = schema_loader.get_schema_for_type(args.type)
        _is_valid, validation_errors = validator.validate(args.type, data, schema)
    except Exception as exc:
        validation_errors = [f"Could not run post-save validation: {exc}"]
    finally:
        if as_json:
            if previous_hide_details is None:
                os.environ.pop("PRISM_STARTUP_HIDE_DETAILS", None)
            else:
                os.environ["PRISM_STARTUP_HIDE_DETAILS"] = previous_hide_details

    if as_json:
        print(
            json.dumps(
                {
                    "success": True,
                    "path": saved_path,
                    "validation_errors": validation_errors or None,
                },
                indent=2,
            )
        )
        return

    print(f"✅ Saved to {saved_path}")
    if validation_errors:
        print(f"⚠ {len(validation_errors)} validation warning(s):")
        for error in validation_errors:
            print(f"  - {error}")
