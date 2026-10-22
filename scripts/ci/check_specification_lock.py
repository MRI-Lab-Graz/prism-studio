"""Fail when the vendored PRISM specification differs from specification.lock.json.

The schemas, terms and spec pages are edited in MRI-Lab-Graz/prism-specification and
carried in this repository by scripts/sync_specification.py. Anything else is drift:
an edited file, a missing file, or a file that is not part of the locked tag.

Usage: check_specification_lock.py [STUDIO_ROOT]   (default: this repository)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SYNC = Path(__file__).resolve().parents[1] / "sync_specification.py"
_spec = importlib.util.spec_from_file_location("sync_specification", _SYNC)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

FIX = "edit it in prism-specification, release a tag, then run scripts/sync_specification.py"


def _vendored_folders() -> list[str]:
    return sorted({target.rsplit("/", 1)[0] + "/" for target in sync.MAPPING.values()})


def check(studio_root: Path, lock: dict) -> list[str]:
    studio_root = Path(studio_root)
    problems: list[str] = []
    locked = lock["files"]
    for rel, expected in sorted(locked.items()):
        path = studio_root / rel
        if not path.is_file():
            problems.append(f"{rel}: missing, but listed in {sync.LOCK_NAME} ({lock['tag']})")
        elif sync.normalized_sha256(path.read_bytes()) != expected:
            problems.append(f"{rel}: differs from {lock['tag']} of {sync.REPOSITORY}; {FIX}")
    for folder in _vendored_folders():
        base = studio_root / folder
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            rel = path.relative_to(studio_root).as_posix()
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
                and rel not in locked
                and rel not in sync.STUDIO_OWNED
            ):
                problems.append(f"{rel}: not part of {lock['tag']} of {sync.REPOSITORY}; {FIX}")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[2]
    lock_path = root / sync.LOCK_NAME
    if not lock_path.is_file():
        print(f"ERROR: {sync.LOCK_NAME} not found in {root}")
        return 1
    problems = check(root, json.loads(lock_path.read_text(encoding="utf-8")))
    for problem in problems:
        print(f"ERROR: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
