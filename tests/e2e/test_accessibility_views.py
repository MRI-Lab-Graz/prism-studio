"""axe-core on the views a page builds only after the user acts, in the WCAG enhanced view: the file-management
tabs and their previews, the validator's expanded error panels, and the survey converter's preview and result."""

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import _new_page
from tests.e2e.test_accessibility_states import serious_violations
from tests.e2e.test_converter_flows import convert_survey, open_survey_tab, select_survey_file
from tests.e2e.test_file_management_flows import (
    WIDE,
    build_two_subjects,
    open_delete_tab,
    open_ids_tab,
    open_wide_to_long,
    preview_subject_rewrite,
    tick_subject,
)
from tests.e2e.test_validate_flows import converted_project, validate_current  # noqa: F401 (fixture)

FILE_MANAGEMENT_TABS = ["renamer", "organizer", "wide-to-long", "rename-ids", "delete"]


@pytest.mark.parametrize("tab", FILE_MANAGEMENT_TABS)
def test_file_management_tab_has_no_accessibility_violations(app_page, studio_url, project, tab):
    build_two_subjects(project)
    app_page.goto(f"{studio_url}/file-management", wait_until="networkidle")
    app_page.click(f"#fm-{tab}-tab")
    app_page.wait_for_selector(f"#fm-{tab}-panel.active")
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the {tab} tab: {found}"


def test_subject_rewrite_preview_has_no_accessibility_violations(app_page, studio_url, project):
    build_two_subjects(project)
    open_ids_tab(app_page, studio_url)
    preview_subject_rewrite(app_page)
    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_enabled(timeout=30000)
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the subject-rewrite preview: {found}"


def test_delete_preview_has_no_accessibility_violations(app_page, studio_url, project):
    build_two_subjects(project)
    open_delete_tab(app_page, studio_url)
    tick_subject(app_page, "sub-1291003")
    app_page.click("#fileDeletePreviewBtn")
    expect(app_page.locator("#fileDeleteApplyBtn")).to_be_enabled(timeout=30000)
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the delete preview: {found}"


def test_wide_to_long_preview_has_no_accessibility_violations(app_page, studio_url, tmp_path):
    open_wide_to_long(app_page, studio_url, tmp_path, WIDE)
    app_page.click("#wideLongDataPreviewBtn")
    expect(app_page.locator("#wideLongTableBody")).to_contain_text("T2", timeout=30000)
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the wide-to-long preview: {found}"


def test_results_page_with_every_panel_open_has_no_accessibility_violations(browser, studio_url, converted_project):
    survey_dir = next(converted_project.glob("sub-*/**/survey"))
    good = next(survey_dir.glob("*_survey.tsv"))
    good.rename(good.with_name(good.name.replace("_survey.tsv", "_survey_oops.tsv")))
    context, page, problems = _new_page(browser, studio_url, converted_project)
    try:
        validate_current(page, studio_url)
        page.wait_for_load_state("networkidle")
        # open every collapsed panel (each error's details, the valid-files list), like a user reading the report
        page.evaluate(
            "document.querySelectorAll('.collapse:not(.show)').forEach(e => bootstrap.Collapse.getOrCreateInstance(e, {toggle: false}).show())"
        )
        page.wait_for_timeout(600)  # the collapse animation
        found = serious_violations(page)
    finally:
        context.close()
    assert found == [], f"axe violations on the results page with every panel open: {found}"
    assert not problems, "\n".join(problems)


@pytest.mark.usefixtures("project_with_demo")
def test_survey_preview_and_result_have_no_accessibility_violations(app_page, studio_url, tmp_path):
    open_survey_tab(app_page, studio_url)
    select_survey_file(app_page, tmp_path)
    app_page.click("#previewBtn")
    expect(app_page.locator("#convertBtn")).to_be_enabled(timeout=30000)
    found = serious_violations(app_page)
    assert found == [], f"axe violations in the survey preview: {found}"
    app_page.click("#convertBtn")
    app_page.wait_for_function(
        "() => !document.getElementById('surveyRunProgressContainer') "
        "|| getComputedStyle(document.getElementById('surveyRunProgressContainer')).display === 'none'",
        timeout=60000,
    )
    found = serious_violations(app_page)
    assert found == [], f"axe violations after the survey conversion: {found}"
