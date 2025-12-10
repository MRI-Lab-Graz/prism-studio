#!/usr/bin/env python3
"""
Add a minimal `Study` block to JSON sidecars under a dataset `rawdata` directory
when it's missing. Intended as a safe, idempotent helper: it will back up
original files with a `.bak` suffix before modifying.

Usage:
  python scripts/fix_rawdata_sidecars.py /path/to/dataset/rawdata

This script is intentionally conservative: it only adds a `Study` object when
it's absent and preserves existing files by creating `.bak` copies.
"""

import sys
import json
from pathlib import Path


def patch_sidecars(rawdata_root):
    root = Path(rawdata_root)
    if not root.exists():
        print(f"Error: path not found: {root}")
        return 1

    patched = 0
    skipped = 0
    for p in root.rglob("*.json"):
        try:
            text = p.read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception as e:
            print(f"Skipping non-json or unreadable file: {p} ({e})")
            skipped += 1
            continue

        if "Study" not in data:
            # Backup original
            bak = p.with_suffix(p.suffix + ".bak")
            if not bak.exists():
                bak.write_text(text, encoding="utf-8")

            # Insert minimal Study block. Use OriginalName if present elsewhere.
            original = data.get("Study", {}).get("OriginalName") if isinstance(data.get("Study"), dict) else None
            if not original:
                # Fallback to filename
                original = p.stem

            data["Study"] = {"OriginalName": original}

            try:
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Patched: {p}")
                patched += 1
            except Exception as e:
                print(f"Failed to write {p}: {e}")
                skipped += 1
        else:
            skipped += 1

    print(f"Done. Patched: {patched}, Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/fix_rawdata_sidecars.py /path/to/dataset/rawdata")
        sys.exit(2)
    sys.exit(patch_sidecars(sys.argv[1]))
