"""Project code maps: ``code/<modality>[_task-X][_ses-Y]_code_map.tsv``.

A map links the codes people typed to participant numbers, so it re-identifies them:
every export asks ``is_code_map`` and git is told to ignore the files (``src.git_exclude``).
"""

from __future__ import annotations

from pathlib import Path


def is_code_map(rel_parts: tuple[str, ...]) -> bool:
    """True for a map, a copy or a backup of one anywhere under ``code/`` (parts relative to the project)."""
    return len(rel_parts) > 1 and rel_parts[0] == "code" and "code_map" in rel_parts[-1].lower()


def find_code_map_files(project_root: str | Path) -> list[str]:
    """Every file ``is_code_map`` names, as sorted posix paths relative to the project."""
    root = Path(project_root)
    found = (p.relative_to(root) for p in (root / "code").rglob("*") if p.is_file())
    return sorted(rel.as_posix() for rel in found if is_code_map(rel.parts))


def left_out_message(paths: list[str]) -> str:
    return "Left out of the export (they re-identify participants): " + ", ".join(paths)
