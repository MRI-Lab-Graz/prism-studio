"""Every Studio page opens with a project selected and raises no browser error.
A new page belongs in tests/e2e/pages.py; a flow that needs clicking gets its own test_<page>_flows.py."""

import pytest

from tests.e2e.pages import PAGES



@pytest.mark.parametrize("path", PAGES)
def test_page_loads_without_browser_errors(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
