"""Flag pull requests that touch app-internal (non-community) schema files.

Advisory helper, not wired into a workflow yet; run it by hand. It is
not blocking (exit code is always 0): app-internal schemas (filename
grammar, project/dataset-description structure) can legitimately need
changes, they just need a core maintainer's eyes rather than the
template-contribution review path.

See docs/superpowers/specs/2026-09-11-modality-contribution-workflow-design.md
section 1.1.
"""

from __future__ import annotations

import os
import subprocess
import sys

RESTRICTED_SCHEMA_FILENAMES = {
    "entities.schema.json",
    "project.schema.json",
    "dataset_description.schema.json",
    "instrument-registry.schema.json",
    "recipe.survey.schema.json",
    "tool-limesurvey.schema.json",
}


def find_restricted_changes(changed_files: list[str]) -> list[str]:
    """Return the subset of changed_files that are restricted schema paths."""
    return [
        path
        for path in changed_files
        if path.startswith("app/schemas/")
        and os.path.basename(path) in RESTRICTED_SCHEMA_FILENAMES
    ]


def get_changed_files(base_ref: str, head_ref: str) -> list[str]:
    """List files changed between base_ref and head_ref via git diff.

    Returns empty list if git diff fails (e.g., shallow checkout with no merge-base).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line for line in result.stdout.splitlines() if line]
    except subprocess.CalledProcessError:
        # Git diff failed (e.g., shallow checkout, missing refs).
        # Return empty list to signal "couldn't determine changes" → advisory flag false.
        return []


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: flag_restricted_schema_changes.py <base_ref> <head_ref>")
        print("(Advisory only, always exits 0)")
        print("RESTRICTED_SCHEMA_CHANGES=false")
        return 0

    changed = get_changed_files(sys.argv[1], sys.argv[2])
    restricted = find_restricted_changes(changed)

    if restricted:
        print("RESTRICTED_SCHEMA_CHANGES=true")
        print("The following file(s) define app behavior, not library content,")
        print("and need a core-maintainer review rather than the template-contribution path:")
        for path in restricted:
            print(f"  - {path}")
    else:
        print("RESTRICTED_SCHEMA_CHANGES=false")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
