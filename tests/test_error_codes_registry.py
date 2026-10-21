"""Every PRISM code the code can emit is in the registry, and every registry code is documented."""

import re
from pathlib import Path

from src.issues import ERROR_CODES

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE = re.compile(r"PRISM\d{3}")


def _emitted():
    codes = set()
    for root in ("src", "app/src"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            if path.name != "issues.py":
                codes |= set(
                    CODE.findall(path.read_text(encoding="utf-8", errors="ignore"))
                )
    return codes


def test_emitted_codes_are_registered():
    missing = _emitted() - set(ERROR_CODES)
    assert not missing, f"add to ERROR_CODES in app/src/issues.py: {sorted(missing)}"


def test_registered_codes_are_documented():
    docs = set(
        CODE.findall(
            (REPO_ROOT / "docs" / "ERROR_CODES.md").read_text(encoding="utf-8")
        )
    )
    missing = set(ERROR_CODES) - docs
    assert not missing, f"add to docs/ERROR_CODES.md: {sorted(missing)}"
