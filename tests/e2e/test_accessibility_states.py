"""axe-core on what test_accessibility.py cannot see at page load, in the WCAG enhanced view:
the hidden converter tabs, every modal, a validator results page, a specification
document page and the states a page shows after load: no project open, an unfinished project, a failed preview
and the item-map dialog."""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import _new_page
from tests.e2e.test_converter_flows import open_survey_tab, select_survey_file
from tests.e2e.test_project_gate_flows import _make_unfinished
from tests.e2e.pages import PAGES
from tests.e2e.test_validate_flows import converted_project, validate_current  # noqa: F401 (fixture)

AXE = Path(__file__).resolve().parents[2] / "node_modules" / "axe-core" / "axe.min.js"
CONVERTER_TABS = ["participants", "survey", "biometrics", "biosample", "physio", "environment"]


def serious_violations(page):
    page.evaluate("document.documentElement.setAttribute('data-wcag', '')")
    page.wait_for_timeout(600)  # let the colour transitions finish before axe measures
    if not page.evaluate("typeof axe !== 'undefined'"):
        page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    return page.evaluate(
        "axe.run({preload: false}).then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => v.id + ' ' + v.nodes.map(n => n.target.join(' ') + (n.any[0] && n.any[0].data && n.any[0].data.contrastRatio ? ' [' + n.any[0].data.contrastRatio + ' ' + n.any[0].data.fgColor + ' on ' + n.any[0].data.bgColor + ']' : '')).join(' | ')))"
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
        # the item-map dialog gets its title (and so its name) from JavaScript when it opens, never bare
        violations = [v for v in serious_violations(app_page) if not (modal == "itemMapModal" and v.startswith("aria-dialog-name"))]
        if violations:
            found[modal] = violations
        app_page.evaluate(f"bootstrap.Modal.getInstance(document.getElementById('{modal}')).hide()")
        app_page.wait_for_selector(f"#{modal}:not(.show)")
    assert found == {}, f"axe violations in modals on {path}: {found}"


@pytest.mark.parametrize("path", PAGES)
def test_page_without_a_project_has_no_accessibility_violations(browser, studio_url, path):
    # Not bare_page: without a project some pages answer 400/409 and log it; this test is about axe only.
    context, page, _ = _new_page(browser, studio_url)
    try:
        page.goto(f"{studio_url}{path}", wait_until="networkidle")
        found = serious_violations(page)
    finally:
        context.close()
    assert found == [], f"axe violations on {path} without a project: {found}"


@pytest.mark.parametrize("path", ["/converter", "/recipes", "/file-management"])
def test_blocked_tool_page_notice_has_no_accessibility_violations(app_page, studio_url, project, path):
    _make_unfinished(project)
    app_page.allowed_http[409] = "/api/"
    app_page.goto(f"{studio_url}{path}", wait_until="networkidle")
    expect(app_page.locator("#prismNotReadyNotice")).to_be_visible()
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the not-ready notice on {path}: {found}"


def test_failed_survey_preview_has_no_accessibility_violations(app_page, studio_url, tmp_path):
    app_page.allowed_http[400] = "/api/survey-workflow-command"
    open_survey_tab(app_page, studio_url)
    select_survey_file(app_page, tmp_path)
    app_page.click("#previewBtn")
    expect(app_page.locator("#convertError")).to_be_visible(timeout=30000)
    found = serious_violations(app_page)
    assert found == [], f"axe violations after a failed preview: {found}"


@pytest.mark.usefixtures("project_with_demo")
def test_item_map_dialog_with_rows_has_no_accessibility_violations(app_page, studio_url, tmp_path):
    app_page.allowed_http[400] = "/api/survey-detect-version-contexts"  # the file matches no template: that is the point
    open_survey_tab(app_page, studio_url)
    # other column names than the template's, so the dialog has rows to match
    select_survey_file(app_page, tmp_path, "participant_id,q1,q2,q3,q4,q5,q6,q7,q8\nP001,3,4,2,0,0,0,0,0\n")
    app_page.click("#itemMapBtn")
    expect(app_page.locator("#itemMapModal [data-role=rows] select").first).to_be_visible(timeout=30000)
    app_page.wait_for_timeout(400)  # the fade-in
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the item-map dialog: {found}"

