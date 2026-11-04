"""Keyboard users must see where they are: the focused control has a visible outline on every page."""

import pytest

from tests.e2e.test_every_page_loads import PAGES


@pytest.mark.parametrize("path", PAGES)
def test_tabbing_shows_a_visible_focus_outline(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    for _ in range(3):
        app_page.keyboard.press("Tab")
    style = app_page.evaluate(
        "(() => { const s = getComputedStyle(document.activeElement);"
        " return [s.outlineStyle, parseFloat(s.outlineWidth), s.boxShadow] })()"
    )
    assert (style[0] != "none" and style[1] >= 2) or style[2] != "none", style
