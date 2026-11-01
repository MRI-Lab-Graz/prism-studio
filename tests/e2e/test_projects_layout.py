"""Projects page layout: fields in one row line up, whatever their label looks like."""

import json

from playwright.sync_api import expect


def _top(page, selector):
    return page.locator(selector).bounding_box()["y"]


def test_study_design_selects_share_one_top_edge(app_page, studio_url):
    page = app_page
    page.set_viewport_size({"width": 1400, "height": 1000})
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", "#smCoreSetupGroupBody", "#smStudyDesign"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()
    # the info icon next to "Timepoints" is added by script: measure only once it is there
    expect(page.locator("#smStudyDesign .info-tip").first).to_be_visible()
    page.wait_for_timeout(300)
    tops = [_top(page, s) for s in ("#smSDType", "#smSDTimepoints", "#smSDConditionType")]
    assert max(tops) - min(tops) <= 1, tops  # a CORE badge, a REQUIRED badge and plain text must not shift the fields


def test_a_dataset_description_error_links_to_the_field_it_names(app_page, studio_url, project):
    # the shared project is complete: drop the fields the test needs the page to complain about
    (project / "project.json").write_text(json.dumps({"Basics": {"Name": "e2e"}}))
    page = app_page
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", "#smCoreSetupGroupBody", "#smBasics"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()
    feedback = page.locator("#metadataValidationFeedback")
    expect(feedback).to_be_visible()
    feedback.get_by_role("link", name="Keywords").first.click()
    expect(page.locator("#metadataKeywords")).to_be_focused()
    feedback.get_by_role("link", name="Authors").first.click()
    expect(page.locator("#metadataAuthorsList .author-first").first).to_be_focused()


def test_project_page_opens_with_all_headings_and_one_score_row(app_page, studio_url):
    page = app_page
    page.goto(f"{studio_url}/projects")
    row = page.locator("#smScoreRow")
    expect(row).to_be_visible()
    expect(row).to_contain_text("Required")
    expect(row).to_contain_text("Core")
    expect(row).to_contain_text("FAIR")
    for target in ("#smCoreSetupGroupBody", "#smRecruitmentExecutionGroupBody", "#smReportingFollowupGroupBody"):
        expect(page.locator(target)).to_be_visible()  # the headings of every section are in view...
    for target in ("#smBasics", "#smOverview", "#smStudyDesign", "#smEligibility", "#smReferences"):
        expect(page.locator(target)).not_to_be_visible()  # ...but none of their fields
    assert page.locator("#smFairRing").count() == 0


def test_required_score_and_save_hint_agree_about_the_corresponding_author(app_page, studio_url):
    # the shared project has an author but nobody marked as corresponding contact: Save asks for that,
    # so the Required tally must not claim everything is done
    page = app_page
    page.goto(f"{studio_url}/projects")
    expect(page.locator("#smScoreRow")).to_contain_text("Required 3/4")
    expect(page.locator("#projectBoxSaveHint, #metadataActionHint").first).to_contain_text("corresponding")
    row = page.locator("#metadataAuthorsList .author-row").first
    if not row.locator(".author-corresponding").is_visible():
        page.locator('[data-bs-target="#smBasics"]').click()
    row.locator(".author-corresponding").check()
    row.locator(".author-email").fill("ada@example.org")
    expect(page.locator("#smScoreRow")).to_contain_text("Required 4/4")
