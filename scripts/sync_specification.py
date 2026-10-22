"""Refresh the vendored PRISM specification from a tagged prism-specification release.

The schemas, term registry and spec pages are edited in
https://github.com/MRI-Lab-Graz/prism-specification and carried here as a plain copy.
This script is the only thing that changes that copy; `specification.lock.json` records
the tag and a sha256 per file, and scripts/ci/check_specification_lock.py fails CI when
the copy and the lock disagree. Stdlib only.

Usage: python scripts/sync_specification.py --tag v1.0.0 [--source DIR] [--studio-root DIR]
  --source  use a local prism-specification checkout instead of downloading the tag
Spec: docs/superpowers/specs/2026-10-22-prism-specification-repo-design.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY = "MRI-Lab-Graz/prism-specification"
LOCK_NAME = "specification.lock.json"

# prism-specification path prefix -> Studio path. Nothing else is copied.
MAPPING = {
    "schemas/": "app/schemas/",
    "terms/": "official/library/terms/",
    "specs/": "docs/specs/",
    "scripts/": "scripts/specification/",
    "LICENSE": "app/schemas/PRISM_SPECIFICATION_LICENSE",
}

# Studio's own formats live in the same folders; sync never writes or deletes them.
STUDIO_OWNED = frozenset(
    [f"app/schemas/{folder}/{name}.schema.json"
     for folder in ("stable", "v0.1", "v0.2")
     for name in ("project", "recipe.survey", "tool-limesurvey", "instrument-registry")]
    + ["app/schemas/README.md", "app/schemas/citation_cff/SOURCE.md", "app/schemas/citation_cff/schema.json",
       "docs/specs/project.md"]
)

_TAG = re.compile(r"^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")
_MAX_ARCHIVE = 64 * 1024 * 1024
_MAX_UNPACKED = 64 * 1024 * 1024


def archive_url(tag: str) -> str:
    if not _TAG.fullmatch(tag):
        raise ValueError(f"not a release tag like v1.0.0: {tag!r}")
    return f"https://github.com/{REPOSITORY}/archive/refs/tags/{tag}.tar.gz"


def normalized_sha256(data: bytes) -> str:
    """Hash with CRLF folded to LF, so a Windows checkout of a text file still matches."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def extract(archive: Path, dest: Path) -> Path:
    """Unpack a GitHub tag archive into dest and return its single top folder.

    Every member is validated first and written by hand (no tarfile.extract): regular
    files and folders only, relative paths without `..`, one top folder `prism-specification-*`.
    """
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        tops = set()
        for m in members:
            parts = Path(m.name).parts
            if m.name.startswith(("/", "\\")) or ".." in parts or not parts:
                raise ValueError(f"unsafe path in archive: {m.name!r}")
            if not (m.isreg() or m.isdir()):
                raise ValueError(f"archive member is not a plain file or folder: {m.name!r}")
            tops.add(parts[0])
        if len(tops) != 1 or not next(iter(tops)).startswith("prism-specification-"):
            raise ValueError(f"archive must hold one folder prism-specification-*, found {sorted(tops)}")
        if sum(m.size for m in members if m.isreg()) > _MAX_UNPACKED:
            raise ValueError("the archive unpacks to more than 64 MB")
        top = dest / next(iter(tops))
        for m in members:
            target = dest / m.name
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(m).read())
    return top


def _destination(rel: str) -> str | None:
    for prefix, target in MAPPING.items():
        if prefix.endswith("/"):
            if rel.startswith(prefix):
                return target + rel[len(prefix):]
        elif rel == prefix:
            return target
    return None


def _is_vendored(rel: str) -> bool:
    """Only paths inside the vendored folders may be deleted because an old lock listed them."""
    if ".." in Path(rel).parts or rel.startswith("/"):
        return False
    return any(rel.startswith(t) if t.endswith("/") else rel == t for t in MAPPING.values())


def _wanted(source: Path) -> dict[str, bytes]:
    """Studio path -> content for every file of the source that is part of the specification."""
    out: dict[str, bytes] = {}
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source).as_posix()
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        target = _destination(rel)
        if target is None:
            continue
        if target in STUDIO_OWNED:
            raise ValueError(f"{rel} is a Studio-owned file; the specification must not carry it")
        data = path.read_bytes()
        if target.startswith("docs/specs/") and target.endswith(".md"):
            data = data.replace(b"](../schemas/", b"](../../app/schemas/")
        out[target] = data
    return out


def sync(source: Path, studio_root: Path, tag: str) -> dict:
    """Write the specification files into Studio and rewrite the lock; return the lock."""
    studio_root = Path(studio_root)
    wanted = _wanted(Path(source))
    if "app/schemas/PRISM_SPECIFICATION_LICENSE" not in wanted or not any(
        rel.startswith("app/schemas/stable/") for rel in wanted
    ):
        # a wrong folder would otherwise delete every vendored file and lock an empty copy
        raise ValueError("the source has no LICENSE and no schemas/stable/: not a prism-specification release")
    lock_path = studio_root / LOCK_NAME
    old = json.loads(lock_path.read_text(encoding="utf-8"))["files"] if lock_path.is_file() else {}
    for rel in sorted(set(old) - set(wanted)):
        if rel not in STUDIO_OWNED and _is_vendored(rel):
            (studio_root / rel).unlink(missing_ok=True)
    for rel, data in wanted.items():
        target = studio_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
    lock = {
        "repository": REPOSITORY,
        "tag": tag,
        "files": {rel: normalized_sha256(data) for rel, data in sorted(wanted.items())},
    }
    lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lock


def download(tag: str, dest: Path) -> Path:
    """Download the tagged archive (https://github.com only) and return the extracted folder."""
    url = archive_url(tag)
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - fixed https github.com URL
        data = response.read(_MAX_ARCHIVE + 1)
    if len(data) > _MAX_ARCHIVE:
        raise ValueError("archive is larger than 64 MB")
    archive = dest / "release.tar.gz"
    archive.write_bytes(data)
    return extract(archive, dest / "src")


def from_git_tag(checkout: Path, tag: str, dest: Path) -> Path:
    """Read `tag` out of a local prism-specification checkout, never its working tree."""
    archive = dest / "release.tar.gz"
    try:
        subprocess.run(
            ["git", "-C", str(checkout), "archive", "--format=tar.gz", f"--prefix=prism-specification-{tag}/",
             "-o", str(archive), tag],
            check=True, capture_output=True, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ValueError(f"cannot read tag {tag} from {checkout}: {detail.strip()}") from exc
    return extract(archive, dest / "src")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True, help="release tag, for example v1.0.0")
    ap.add_argument("--source", type=Path, help="local prism-specification git checkout; the tag is read from it (skips the download)")
    ap.add_argument("--studio-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args(argv)
    archive_url(args.tag)  # reject odd tags before anything runs
    try:
        with tempfile.TemporaryDirectory() as tmp:
            source = from_git_tag(args.source, args.tag, Path(tmp)) if args.source else download(args.tag, Path(tmp))
            lock = sync(source, args.studio_root, args.tag)
    except (ValueError, OSError, tarfile.TarError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"synced {len(lock['files'])} files from {REPOSITORY} {args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
