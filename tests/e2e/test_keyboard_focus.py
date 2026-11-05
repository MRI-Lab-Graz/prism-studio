"""Keyboard users must see where they are: in the WCAG enhanced view, the focused control has a visible outline on every page."""

import pytest

from tests.e2e.pages import PAGES


@pytest.mark.parametrize("path", PAGES)
def test_tabbing_shows_a_visible_focus_outline(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    # the WCAG enhanced view is the Settings switch "wcag_enhanced_view" (off by default); this is the "on" look
    app_page.evaluate("document.documentElement.setAttribute('data-wcag', '')")
    for _ in range(3):
        app_page.keyboard.press("Tab")
    style = app_page.evaluate(
        "(() => { const s = getComputedStyle(document.activeElement);"
        " return [s.outlineStyle, parseFloat(s.outlineWidth), s.boxShadow] })()"
    )
    assert (style[0] != "none" and style[1] >= 2) or style[2] != "none", style


@pytest.mark.parametrize("path", PAGES)
def test_first_tab_stop_is_a_skip_link_to_the_main_content(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    app_page.keyboard.press("Tab")
    first = app_page.evaluate("[document.activeElement.getAttribute('href'), document.activeElement.textContent.trim()]")
    assert first == ["#main-content", "Skip to main content"], first
    assert app_page.evaluate("!!document.querySelector('main#main-content')")
