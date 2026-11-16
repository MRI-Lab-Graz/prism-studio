"""axe-core on what test_accessibility.py cannot see at page load, in the WCAG enhanced view:
the hidden converter tabs, every modal, a validator results page and a specification document page."""

import pytest

from tests.e2e.conftest import _new_page
from tests.e2e.pages import PAGES
from tests.e2e.test_accessibility import AXE
from tests.e2e.test_validate_flows import converted_project, validate_current  # noqa: F401 (fixture)

# The item-map dialog gets its title (and so its name) from JavaScript when it opens, never bare.
TITLED_AT_RUNTIME = {"itemMapModal"}
CONVERTER_TABS = ["participants", "survey", "biometrics", "biosample", "physio", "environment"]


def serious_violations(page):
    page.evaluate("document.documentElement.setAttribute('data-wcag', '')")
    page.wait_for_timeout(600)  # let the colour transitions finish before axe measures
    if not page.evaluate("typeof axe !== 'undefined'"):
        page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    return page.evaluate(
        "axe.run({preload: false}).then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => v.id + ' ' + v.nodes.map(n => n.target.join(' ')).join(' | ')))"
    )


@pytest.mark.parametrize("tab", CONVERTER_TABS)
def test_converter_tab_has_no_accessibility_violations(app_page, studio_url, tab):
    app_page.goto(f"{studio_url}/converter", wait_until="networkidle")
    app_page.click(f"#{tab}-tab")
    app_page.wait_for_selector(f"#{tab}-panel.active")
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the {tab} tab: {found}"


def test_specification_document_page_has_no_accessibility_violations(app_page, studio_url):
    app_page.goto(f"{studio_url}/specifications/survey", wait_until="networkidle")
    found = serious_violations(app_page)
    assert found == [], f"axe violations on /specifications/survey: {found}"


def test_validation_results_page_has_no_accessibility_violations(browser, studio_url, converted_project):
    context, page, problems = _new_page(browser, studio_url, converted_project)
    try:
        validate_current(page, studio_url)
        page.wait_for_load_state("networkidle")
        found = serious_violations(page)
    finally:
        context.close()
    assert found == [], f"axe violations on the results page: {found}"
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", PAGES)
def test_every_modal_has_no_accessibility_violations(app_page, studio_url, path):
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    modals = app_page.evaluate("[...document.querySelectorAll('.modal')].map(m => m.id)")
    found = {}
    for modal in modals:
        app_page.evaluate(f"bootstrap.Modal.getOrCreateInstance(document.getElementById('{modal}')).show()")
        app_page.wait_for_selector(f"#{modal}.show")
        app_page.wait_for_timeout(400)  # the fade-in
        violations = [v for v in serious_violations(app_page) if not (modal in TITLED_AT_RUNTIME and v.startswith('aria-dialog-name'))]
        if violations:
            found[modal] = violations
        app_page.evaluate(f"bootstrap.Modal.getInstance(document.getElementById('{modal}')).hide()")
        app_page.wait_for_selector(f"#{modal}:not(.show)")
    assert found == {}, f"axe violations in modals on {path}: {found}"
