"""Projects page: every add-a-row control is a draft (green check, Cancel) until accepted;
the red cross only appears on defined rows."""

import json
import re

from playwright.sync_api import expect


def open_sections(page, studio_url, *targets):
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", *targets):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()


def test_a_new_list_row_is_a_draft_until_accepted(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    page.click("#smEligInclusionAdd")
    row = page.locator("#smEligInclusionList .overview-list-row").last
    badge = page.locator("#smEligCriteriaRequiredBadge")

    expect(row.locator('[data-f="accept"]')).to_be_disabled()  # nothing typed yet
    expect(row.locator('[data-f="remove"]')).to_have_count(0)
    row.locator(".overview-list-input").fill("Adults aged 18 to 35")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    assert page.input_value("#smEligInclusion") == ""  # a draft is not part of the form yet
    expect(badge).not_to_have_class(re.compile("bg-success"))

    row.locator('[data-f="accept"]').click()
    expect(row.locator('[data-f="remove"]')).to_have_count(1)
    expect(row.locator('[data-f="accept"]')).to_have_count(0)
    assert page.input_value("#smEligInclusion") == "Adults aged 18 to 35"
    expect(badge).to_have_class(re.compile("bg-success"))

    page.click("#smEligInclusionAdd")
    second = page.locator("#smEligInclusionList .overview-list-row").last
    second.locator(".overview-list-input").fill("not wanted")
    second.locator('[data-f="cancel"]').click()
    expect(page.locator("#smEligInclusionList .overview-list-row")).to_have_count(2)  # accepted + placeholder
    assert page.input_value("#smEligInclusion") == "Adults aged 18 to 35"


def test_loaded_list_rows_are_defined(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"InclusionCriteria": ["Adults", "Healthy"]}
    (project / "project.json").write_text(json.dumps(meta))
    open_sections(app_page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    rows = app_page.locator("#smEligInclusionList .overview-list-row")
    expect(rows).to_have_count(2)
    expect(app_page.locator('#smEligInclusionList [data-f="remove"]')).to_have_count(2)
    expect(app_page.locator('#smEligInclusionList [data-f="accept"]')).to_have_count(0)


def test_two_field_rows_use_the_same_draft_and_accept_rule(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smMissingData")
    page.click("#smKnownIssuesAddRow")
    row = page.locator("#smKnownIssuesList .two-field-row").last
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    row.locator(".two-field-input-1").fill("sub-002_task-nback_bold.nii")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    assert page.input_value("#smKnownIssues") == ""
    row.locator('[data-f="accept"]').click()
    expect(row.locator('[data-f="remove"]')).to_have_count(1)
    assert page.input_value("#smKnownIssues") == "sub-002_task-nback_bold.nii"


def test_doi_rows_keep_the_lookup_as_a_helper_next_to_the_check(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smReferences")
    page.click("#smReferencesAdd")
    row = page.locator("#smReferencesList .overview-list-row").last
    row.locator(".overview-list-input").fill("10.1000/xyz123")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    expect(row.locator('[data-f="remove"]')).to_have_count(0)
    row.locator('[data-f="accept"]').click()
    expect(row.locator('[data-f="remove"]')).to_have_count(1)
    expect(row.locator('button[aria-label="Check DOI"]')).to_be_hidden()  # helper only for drafts
    assert "10.1000/xyz123" in page.input_value("#smReferencesText")


def test_a_malformed_doi_cannot_be_accepted(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smReferences")
    page.click("#smReferencesAdd")
    row = page.locator("#smReferencesList .overview-list-row").last
    row.locator(".overview-list-input").fill("not a doi")
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
