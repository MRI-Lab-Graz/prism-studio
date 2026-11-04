"""axe-core on every Studio page: no serious or critical accessibility violation."""

from pathlib import Path

import pytest

from tests.e2e.pages import PAGES

AXE = Path(__file__).resolve().parents[2] / "node_modules" / "axe-core" / "axe.min.js"


@pytest.mark.parametrize("path", PAGES)
def test_page_has_no_accessibility_violations(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    app_page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    found = app_page.evaluate(
        "axe.run({preload: false}).then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => v.id))"
    )
    assert found == [], f"axe violations on {path}: {found}"
