"""The release procedure (docs/SCHEMA_VERSIONING.md) commits old schema versions to app/schemas/archive/.

A global `archive/` rule in .gitignore hid that folder, so the CI job `Modality schema versions`
could never see an archived copy and a bumped schema could never pass it.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_schema_archive_folder_is_not_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "app/schemas/archive/biosample/1.0.0.schema.json"],
        cwd=ROOT,
    )
    assert result.returncode == 1, "app/schemas/archive/ is ignored by git (exit 0); add a negation to .gitignore"
