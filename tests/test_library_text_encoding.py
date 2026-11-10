"""Official library templates must not contain mojibake (UTF-8 text decoded as Latin-1/cp1252)."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "official" / "library"
FILES = sorted(ROOT.rglob("*.json"))


def mojibake_fix(s):
    """The repaired text if `s` is UTF-8 that was decoded as Latin-1/cp1252, else None."""
    if not any(c in s for c in "ÃÂâ"):
        return None
    for enc in ("latin-1", "cp1252"):
        try:
            fixed = s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if fixed != s:
            return fixed
    return None


def strings(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from strings(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from strings(v, f"{path}[{i}]")
    elif isinstance(o, str):
        yield path, o


@pytest.mark.parametrize("f", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_mojibake(f):
    data = json.loads(f.read_text(encoding="utf-8"))
    bad = [f"{p}: {s[:50]!r}" for p, s in strings(data) if mojibake_fix(s)]
    assert not bad, bad


INITIALS = re.compile(r"^(?:[A-Z]\.?\s?)+$")
SURVEYS = [f for f in FILES if f.name.startswith("survey-")]


@pytest.mark.parametrize("f", SURVEYS, ids=lambda p: p.name)
def test_authors_are_whole_names_not_comma_fragments(f):
    """Study/Authors holds one entry per author ("Kroenke, K."), not the citation cut at every comma."""
    authors = json.loads(f.read_text(encoding="utf-8")).get("Study", {}).get("Authors", [])
    bad = [a for a in authors if a.startswith("&") or INITIALS.match(a)]
    assert not bad, bad
