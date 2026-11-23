"""Turn a full survey template into a stub: all facts and item fingerprints, no instrument text.

Usage: python scripts/make_stub.py TEMPLATE.json [-o STUB.json]   (prints to stdout without -o)
Removed: item Description, Levels labels (the keys stay), Help, OtherOption.label, VariantScales Levels,
Study.Instructions and the instruction/bibliographic sections of Study.ArchiveMetadata that are quoted text.
Added: Study.ItemTextsIncluded false and, per item, Fingerprint (scripts/fingerprint.py).
See specs/instrument-ids.md. The result still needs its licence fields checked (scripts/check_library.py).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from check_library import ARCHIVE_TEXT_EXEMPT, NON_ITEMS
from fingerprint import template_fingerprints


def make_stub(data: dict) -> dict:
    study = data.get("Study") or {}
    if study.get("ItemTextsIncluded") is False:
        raise ValueError("already a stub")
    prints = template_fingerprints(data)
    stub = copy.deepcopy(data)
    stub_study = stub.setdefault("Study", {})
    stub_study["ItemTextsIncluded"] = False
    stub_study.pop("Instructions", None)
    archive = stub_study.get("ArchiveMetadata")
    if isinstance(archive, dict):
        stub_study["ArchiveMetadata"] = {k: v for k, v in archive.items() if k not in ARCHIVE_TEXT_EXEMPT}
    for key, item in stub.items():
        if key in NON_ITEMS or not isinstance(item, dict) or "AliasOf" in item:
            continue
        item["Description"] = None
        if isinstance(item.get("Levels"), dict):
            item["Levels"] = dict.fromkeys(item["Levels"])
        item.pop("Help", None)
        if isinstance(item.get("OtherOption"), dict):
            item["OtherOption"].pop("label", None)
        for scale in item.get("VariantScales") or []:
            if isinstance(scale, dict):
                scale.pop("Levels", None)
        if key in prints:
            item["Fingerprint"] = prints[key]
    return stub


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("template")
    ap.add_argument("-o", "--output")
    args = ap.parse_args(argv)
    try:
        stub = make_stub(json.loads(Path(args.template).read_text(encoding="utf-8")))
    except ValueError as exc:
        print(f"{args.template}: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(stub, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
