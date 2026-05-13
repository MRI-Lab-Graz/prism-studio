"""Export a PRISM project as a reusable template ZIP.

The template export keeps project metadata and configuration while excluding
participant-specific content such as subject folders and participant tables.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Any

TEMPLATE_EXCLUDED_ROOT_FILES = {
    "participants.tsv",
    "participants.json",
    "participants_mapping.json",
}

TEMPLATE_EXCLUDED_FILENAMES = {
    "participants_mapping.json",
    "anonymization_map.json",
}


def _write_tree(
    archive: zipfile.ZipFile,
    source_root: Path,
    arc_prefix: str,
    stats: dict[str, int],
) -> None:
    """Write a folder tree into a ZIP archive while excluding participant files."""
    for root, dirs, files in os.walk(source_root):
        before = len(dirs)
        dirs[:] = [d for d in dirs if not d.startswith("sub-")]
        stats["subject_dirs_skipped"] += before - len(dirs)

        rel_root = Path(root).relative_to(source_root)
        for filename in files:
            if filename in TEMPLATE_EXCLUDED_FILENAMES:
                stats["files_skipped"] += 1
                continue
            source_file = Path(root) / filename
            arcname = str(Path(arc_prefix) / rel_root / filename)
            archive.write(source_file, arcname)
            stats["files_written"] += 1


def export_project_template_zip(project_path: Path, output_zip: Path) -> dict[str, Any]:
    """Create a project template ZIP without deleting or changing source files."""
    project_root = project_path.expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise ValueError(f"Project path does not exist: {project_root}")

    output_path = output_zip.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats: dict[str, int] = {
        "files_written": 0,
        "files_skipped": 0,
        "subject_dirs_skipped": 0,
        "root_subject_dirs_skipped": 0,
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(project_root.iterdir()):
            if item.resolve() == output_path:
                continue

            if item.is_dir():
                if item.name.startswith("sub-"):
                    stats["root_subject_dirs_skipped"] += 1
                    continue
                _write_tree(archive, item, item.name, stats)
                continue

            if item.name in TEMPLATE_EXCLUDED_ROOT_FILES:
                stats["files_skipped"] += 1
                continue
            if item.name in TEMPLATE_EXCLUDED_FILENAMES:
                stats["files_skipped"] += 1
                continue

            archive.write(item, item.name)
            stats["files_written"] += 1

    return {
        "project_path": str(project_root),
        "output_zip": str(output_path),
        **stats,
    }
