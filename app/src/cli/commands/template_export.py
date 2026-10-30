"""Template export command handler for prism_tools CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def cmd_template_export(args) -> None:
    """Create a template ZIP from a project without participant data (after the validation Studio runs, too)."""
    from src.export_options import ExportBlocked, run_template_export

    project_path = Path(args.project).expanduser().resolve()
    data = {"validation_mode": getattr(args, "validation_mode", "both") or "both", "output_folder": getattr(args, "output_folder", None)}
    output_zip = Path(args.output).expanduser().resolve() if getattr(args, "output", None) else None
    try:
        stats = run_template_export(project_path, data, output_zip)
    except ExportBlocked as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error creating template ZIP: {exc}")
        sys.exit(1)

    if bool(getattr(args, "json", False)):
        print(json.dumps({"success": True, **stats}, ensure_ascii=False))
        return

    print("✅ Project template export complete")
    print(f"   Output ZIP: {stats['output_zip']}")
    print(f"   Files written: {stats['files_written']}")
    print(f"   Files skipped: {stats['files_skipped']}")
    print(f"   Subject dirs skipped: {stats['subject_dirs_skipped']}")
    print(f"   Root subject dirs skipped: {stats['root_subject_dirs_skipped']}")
