import json
import re

from playwright.sync_api import expect

AGE = {"id": "age", "label": "Age", "term": "nb:Age", "type": "numeric",
       "mode": "include", "min": 18, "max": 35, "unit": "years"}


def test_eligibility_criteria_load_edit_and_save(app_page, studio_url, project):
    """Criteria in project.json show as rows; a criterion added in the form is saved back."""
    page = app_page
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"Criteria": [AGE]}
    (project / "project.json").write_text(json.dumps(meta))
    page.goto(f"{studio_url}/projects")

    for target in ("#studyMetadataSection", "#smRecruitmentExecutionGroupBody", "#smEligibility"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()
    rows = page.locator("#smEligCriteriaList [data-i]")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Age")
    expect(rows.first.locator('[data-f="min"]')).to_have_value("18")

    page.select_option("#smEligCriteriaSelect", label="Sex")
    page.click("#smEligCriteriaAdd")
    expect(rows).to_have_count(2)
    rows.nth(1).locator('[data-f="mode"]').select_option("exclude")
    rows.nth(1).locator('[data-f="value"][value="Male"]').check()
    rows.nth(1).locator('[data-f="accept"]').click()

    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()  # required fields still missing
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    saved = json.loads((project / "project.json").read_text())["Eligibility"]["Criteria"]
    assert saved[0] == AGE
    assert saved[1] == {"id": "sex", "label": "Sex", "term": "nb:Sex", "type": "categorical",
                        "mode": "exclude", "values": ["Male"]}


def _open_eligibility(page, studio_url):
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", "#smRecruitmentExecutionGroupBody", "#smEligibility"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()


def test_new_criterion_is_a_draft_with_an_accept_icon_and_turns_core_green_when_accepted(app_page, studio_url):
    page = app_page
    _open_eligibility(page, studio_url)
    row = page.locator("#smEligCriteriaList [data-i]")
    inclusion_badge = page.locator("#smEligCriteriaRequiredBadge")
    expect(inclusion_badge).not_to_have_class(re.compile("bg-success"))

    page.select_option("#smEligCriteriaSelect", label="Age")
    page.click("#smEligCriteriaAdd")
    # a draft: accept (disabled until complete) and cancel, no red delete cross yet
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    expect(row.locator('[data-f="remove"]')).to_have_count(0)
    row.locator('[data-f="min"]').fill("18")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    expect(inclusion_badge).not_to_have_class(re.compile("bg-success"))  # not accepted yet

    row.locator('[data-f="accept"]').click()
    expect(row.locator('[data-f="remove"]')).to_have_count(1)  # defined: now it can be deleted
    expect(row.locator('[data-f="accept"]')).to_have_count(0)
    expect(inclusion_badge).to_have_class(re.compile("bg-success"))

    row.locator('[data-f="remove"]').click()
    expect(row).to_have_count(0)
    expect(inclusion_badge).not_to_have_class(re.compile("bg-success"))


def test_accepted_exclude_criterion_turns_the_exclusion_badge_green_and_a_draft_can_be_cancelled(app_page, studio_url):
    page = app_page
    _open_eligibility(page, studio_url)
    row = page.locator("#smEligCriteriaList [data-i]")
    exclusion_badge = page.locator("#smEligExclusionOptionalBadge")

    page.select_option("#smEligCriteriaSelect", label="Sex")
    page.click("#smEligCriteriaAdd")
    row.locator('[data-f="mode"]').select_option("exclude")
    row.locator('[data-f="value"][value="Male"]').check()
    row.locator('[data-f="accept"]').click()
    expect(exclusion_badge).to_have_class(re.compile("bg-success"))

    page.select_option("#smEligCriteriaSelect", label="Handedness")
    page.click("#smEligCriteriaAdd")
    expect(row).to_have_count(2)
    row.nth(1).locator('[data-f="cancel"]').click()
    expect(row).to_have_count(1)
