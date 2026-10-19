"""Projects page layout: fields in one row line up, whatever their label looks like."""

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
    expect(page.locator("#smStudyDesign .field-hint-trigger").first).to_be_visible()
    page.wait_for_timeout(300)
    tops = [_top(page, s) for s in ("#smSDType", "#smSDTimepoints", "#smSDConditionType")]
    assert max(tops) - min(tops) <= 1, tops  # a CORE badge, a REQUIRED badge and plain text must not shift the fields


def test_a_dataset_description_error_links_to_the_field_it_names(app_page, studio_url):
    page = app_page
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", "#smCoreSetupGroupBody"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()
    feedback = page.locator("#metadataValidationFeedback")
    expect(feedback).to_be_visible()
    feedback.get_by_role("link", name="Keywords").first.click()
    expect(page.locator("#metadataKeywords")).to_be_focused()
    feedback.get_by_role("link", name="Authors").first.click()
    expect(page.locator("#metadataAuthorsList .author-first").first).to_be_focused()
