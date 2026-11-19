"""official/library/NOTICE.md must describe what the library really holds (it was once stale)."""

import json
import re
from pathlib import Path

LIBRARY = Path(__file__).resolve().parent.parent / "official" / "library"


def test_the_notice_counts_the_shipped_templates_by_licence():
    notice = (LIBRARY / "NOTICE.md").read_text(encoding="utf-8")
    licences = [json.loads(p.read_text(encoding="utf-8"))["Study"].get("LicenseID")
                for p in sorted((LIBRARY / "survey").glob("survey-*.json"))]
    assert f"## What ships ({len(licences)} templates)" in notice
    assert f"- {licences.count('CC-BY-SA-4.0')} templates of the Open Test Archive" in notice
    assert licences.count("CC0-1.0") == 1 and licences.count("Other") == 2  # demo, and the two DASS templates
    assert not re.search(r"contains only|only templates that may", notice)
