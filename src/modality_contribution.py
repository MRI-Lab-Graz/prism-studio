"""Build minimal valid PRISM datasets for a proposed modality or template.

Shared by the CI contribution-contract check and the Issue-Form-to-draft-PR
bot (spec: docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md,
section 1.2 item 3) so the manual and guided contribution paths produce and
are held to the exact same dataset shape.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_minimal_dataset(
    dest_dir: Path,
    *,
    suffix: str,
    extension: str,
    sidecar: dict,
    data_content: str,
    task_name: str = "demo",
) -> Path:
    """Write a minimal valid PRISM dataset for one subject/modality.

    Creates dataset_description.json and sub-01/<suffix>/ containing the
    data file plus its matching JSON sidecar. Returns the path to the
    created data file.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dataset_description = {
        "Name": "PRISM Contribution Fixture",
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Authors": ["prism-contribution-fixture"],
        "Keywords": ["prism", "contribution-fixture", "template"],
    }
    (dest_dir / "dataset_description.json").write_text(
        json.dumps(dataset_description, indent=2), encoding="utf-8"
    )

    modality_dir = dest_dir / "sub-01" / suffix
    modality_dir.mkdir(parents=True, exist_ok=True)

    stem = f"sub-01_task-{task_name}_{suffix}"
    data_path = modality_dir / f"{stem}.{extension}"
    data_path.write_text(data_content, encoding="utf-8")

    sidecar_path = modality_dir / f"{stem}.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    return data_path
