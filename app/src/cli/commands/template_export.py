"""Template export command handler for prism_tools CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.project_template_export import export_project_template_zip


def cmd_template_export(args) -> None:
    """Create a template ZIP from a project without participant data."""
    project_path = Path(args.project).expanduser().resolve()
    output_zip = Path(args.output).expanduser().resolve()

    try:
        stats = export_project_template_zip(project_path, output_zip)
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
