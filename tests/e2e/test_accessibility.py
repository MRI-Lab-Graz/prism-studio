"""axe-core on every Studio page: no accessibility rule may fail that is not in the baseline.
The baseline (a11y_baseline.json) lists the known failures per page; shrink it, never grow it (a fixed rule must be removed: the test fails on stale entries)."""

import json
from pathlib import Path

import pytest

from tests.e2e.pages import PAGES

AXE = Path(__file__).resolve().parents[2] / "node_modules" / "axe-core" / "axe.min.js"
BASELINE = Path(__file__).with_name("a11y_baseline.json")


@pytest.mark.parametrize("path", PAGES)
def test_page_has_no_new_accessibility_violations(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    app_page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    found = app_page.evaluate(
        "axe.run({preload: false}).then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => v.id))"
    )
    known = json.loads(BASELINE.read_text()).get(path, [])
    assert sorted(set(known) - set(found)) == [], f"fixed on {path}: remove from a11y_baseline.json"
    assert sorted(set(found) - set(known)) == [], f"new axe violations on {path}"
