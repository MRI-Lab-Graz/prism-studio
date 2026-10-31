"""The one writer of a dataset's dataset_description.json.

project.json mirrors the dataset-level metadata (name, keywords, authors, ...) of dataset_description.json.
If two pieces of code wrote the two files independently they would drift apart ("project.json name does not
match dataset_description.json Name"), so every code path writes the file here: the file first, then the
mirror. tests/test_single_dataset_description_writer.py fails on any other writer.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_dataset_description(project_root: str | Path, description: dict, *, mirror: bool = True) -> Path:
    """Write `description` as <project_root>/dataset_description.json and mirror it into project.json.

    `mirror=False` is for a converter that writes placeholder defaults (e.g. "PRISM Survey Dataset"): those
    must not become the project's name. Without a project.json there is nothing to mirror.
    """
    root = Path(project_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "dataset_description.json"
    path.write_text(json.dumps(description, indent=2, ensure_ascii=False), encoding="utf-8")
    if mirror and (root / "project.json").exists():
        from src.project_manager import ProjectManager  # lazy: only a project has a mirror

        ProjectManager().sync_dataset_metadata_to_project_json(root, description)
    return path
