"""Fingerprint item texts (SHA-256 of the normalised text) for stubs: specs/instrument-ids.md.

Usage: python scripts/fingerprint.py TEMPLATE.json
Prints {"<item>": {"<language>": "sha256:<hex>"}} for every item of the template that carries text.
Normalisation (never change it: every published fingerprint depends on it): Unicode NFC, case-folded,
punctuation, symbols and invisible format characters removed, whitespace collapsed to single spaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

from check_library import NON_ITEMS


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = "".join(c for c in text if unicodedata.category(c)[0] not in "PSC" or c in "\t\n\r")
    return " ".join(text.split())


def fingerprint(text: str) -> str:
    return "sha256:" + hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def template_fingerprints(data: dict) -> dict:
    """Item -> language -> fingerprint of Description; a plain string belongs to Technical.Language."""
    if (data.get("Study") or {}).get("ItemTextsIncluded") is False:
        return {}
    default = (data.get("Technical") or {}).get("Language")
    out = {}
    for key, item in data.items():
        text = item.get("Description") if key not in NON_ITEMS and isinstance(item, dict) else None
        if isinstance(text, str) and default:
            text = {default: text}
        if isinstance(text, dict):
            out[key] = {lang: fingerprint(t) for lang, t in text.items() if isinstance(t, str)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("template")
    data = json.loads(Path(ap.parse_args(argv).template).read_text(encoding="utf-8"))
    print(json.dumps(template_fingerprints(data), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
