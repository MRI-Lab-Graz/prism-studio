"""The validator page, checked against the WCAG 2.2 AA points axe cannot decide on its own."""

from tests.e2e.test_accessibility import AXE

URL = "/validate"


def test_the_page_has_one_h1(app_page, studio_url):
    app_page.goto(f"{studio_url}{URL}", wait_until="networkidle")
    assert app_page.locator("h1").count() == 1


def test_no_aria_attribute_is_used_where_it_is_not_allowed(app_page, studio_url):
    app_page.goto(f"{studio_url}{URL}", wait_until="networkidle")
    app_page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    nodes = app_page.evaluate(
        "axe.run({preload: false, runOnly: ['aria-prohibited-attr']})"
        ".then(r => [...r.violations, ...r.incomplete].flatMap(v => v.nodes.map(n => n.html.slice(0, 80))))"
    )
    assert nodes == []


def test_links_in_running_text_are_underlined(app_page, studio_url):
    app_page.goto(f"{studio_url}{URL}", wait_until="networkidle")
    app_page.evaluate("document.documentElement.setAttribute('data-wcag', '')")  # these rules belong to the WCAG enhanced view
    plain = app_page.evaluate(
        "[...document.querySelectorAll('p a, li a, small a')]"
        ".filter(a => !a.closest('.btn, .badge, .nav-link, .dropdown-item, nav')"
        " && !getComputedStyle(a).textDecorationLine.includes('underline')).map(a => a.outerHTML.slice(0, 80))"
    )
    assert plain == []


def test_tabbing_never_hides_the_focused_control_behind_the_sticky_navbar(app_page, studio_url):
    app_page.goto(f"{studio_url}{URL}", wait_until="networkidle")
    app_page.evaluate("document.documentElement.setAttribute('data-wcag', '')")  # these rules belong to the WCAG enhanced view
    bar = app_page.evaluate("document.querySelector('nav.sticky-top').getBoundingClientRect().bottom")
    # Chromium centres a focused control by itself; Firefox and Safari scroll it only as far as the edge,
    # which would leave it under the bar unless the page reserves the bar's height.
    reserved = app_page.evaluate("parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0")
    assert reserved >= bar, (reserved, bar)
    app_page.set_viewport_size({"width": 1600, "height": 400})  # short window: the page must scroll
    hidden = []
    for _ in range(80):
        app_page.keyboard.press("Tab")
        top = app_page.evaluate(
            "(() => { const e = document.activeElement; const r = e.getBoundingClientRect();"
            " return e === document.body || e.closest('nav.sticky-top, .visually-hidden-focusable') ? null : [r.top, e.outerHTML.slice(0, 70)] })()"
        )
        if top is not None and top[0] < bar:
            hidden.append(top)
    assert hidden == []
