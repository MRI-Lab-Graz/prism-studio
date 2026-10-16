"""Fail when a frozen modality schema version is edited or a version is released wrongly.

Usage: check_schema_versions.py <base_ref> <head_ref>
Rules (modality schemas only; project/entities/dataset_description are not versioned this way):
- files under app/schemas/archive/ are frozen: never modified or deleted;
- a changed stable schema must carry a bumped `version`;
- a bumped version needs the previous version archived, equal to the previous stable file.
"""

from __future__ import annotations

import json
import subprocess
import sys

STABLE = "app/schemas/stable/"
ARCHIVE = "app/schemas/archive/"
SUFFIX = ".schema.json"


def _version(text: str | None) -> str | None:
    try:
        return json.loads(text)["version"] if text else None
    except (ValueError, KeyError, TypeError):
        return None


def _same(a: str | None, b: str | None) -> bool:
    try:
        return json.loads(a) == json.loads(b)
    except (ValueError, TypeError):
        return False


def check(changes, read_base, read_head, exists_head, modalities) -> list[str]:
    errors: list[str] = []
    for status, path in changes:
        if path.startswith(ARCHIVE) and status in ("M", "D"):
            errors.append(f"{path}: archived versions are frozen and must not be edited or deleted")
            continue
        if not (path.startswith(STABLE) and path.endswith(SUFFIX) and status == "M"):
            continue
        name = path[len(STABLE) : -len(SUFFIX)]
        if name not in modalities:
            continue
        old, new = _version(read_base(path)), _version(read_head(path))
        if old is not None and old == new:
            errors.append(f"{path}: content changed but `version` is still {old}; bump it")
        elif old is not None and new is not None:
            archived = f"{ARCHIVE}{name}/{old}{SUFFIX}"
            if not exists_head(archived):
                errors.append(f"{path}: version {old} must be copied to {archived} before it changes (archive)")
            elif not _same(read_head(archived), read_base(path)):
                errors.append(f"{archived}: differs from the previous {path}; archive an exact copy")
    return errors


def _git_show(ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def main(argv: list[str]) -> int:
    base, head = argv[1], argv[2]
    diff = subprocess.run(
        ["git", "diff", "--name-status", f"{base}...{head}"], capture_output=True, text=True, check=True
    ).stdout
    changes = [tuple(line.split("\t", 1)) for line in diff.splitlines() if "\t" in line]
    entities = _git_show(head, "app/schemas/stable/entities.schema.json")
    modalities = set(json.loads(entities)["modalities"]) if entities else set()
    errors = check(
        changes,
        lambda p: _git_show(base, p),
        lambda p: _git_show(head, p),
        lambda p: _git_show(head, p) is not None,
        modalities,
    )
    for message in errors:
        print(f"ERROR: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
