"""axe-core on every Studio page in the WCAG enhanced view: no serious or critical accessibility violation."""

import pytest

from tests.e2e.pages import PAGES
from tests.e2e.test_accessibility_states import serious_violations


@pytest.mark.parametrize("path", PAGES)
def test_page_has_no_accessibility_violations(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    found = serious_violations(app_page)  # in the WCAG enhanced view (Settings switch, off by default)
    assert found == [], f"axe violations on {path}: {found}"
