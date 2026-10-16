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
    chips = page.locator("#smEligCriteriaList .chip-badge")
    expect(chips).to_have_count(1)
    expect(chips.first).to_contain_text("Age · include 18–35 years")

    page.select_option("#smEligCriteriaSelect", label="Sex")
    page.click("#smEligCriteriaAdd")
    draft = page.locator("#smEligCriteriaList [data-i]")
    expect(draft).to_have_count(1)  # accepted criteria are chips; only the new one is an entry row
    draft.locator('[data-f="mode"]').select_option("exclude")
    draft.locator('[data-f="value"][value="Male"]').check()
    draft.locator('[data-f="accept"]').click()
    expect(chips).to_have_count(2)
    expect(chips.nth(1)).to_contain_text("Sex · exclude Male")

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
    chip = page.locator("#smEligCriteriaList .chip-badge")
    expect(row).to_have_count(0)  # the entry row is gone: the criterion is now a green chip
    expect(chip).to_have_count(1)
    expect(chip.first).to_contain_text("Age · include ≥ 18 years")
    expect(inclusion_badge).to_have_class(re.compile("bg-success"))

    chip.first.click()  # clicking the chip removes it
    expect(chip).to_have_count(0)
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
    expect(page.locator("#smEligCriteriaList .chip-badge")).to_have_count(1)

    page.select_option("#smEligCriteriaSelect", label="Handedness")
    page.click("#smEligCriteriaAdd")
    expect(row).to_have_count(1)
    row.locator('[data-f="cancel"]').click()
    expect(row).to_have_count(0)
    expect(page.locator("#smEligCriteriaList .chip-badge")).to_have_count(1)  # the accepted one stays


def test_the_criteria_select_starts_on_a_placeholder_and_returns_to_it_after_adding(app_page, studio_url):
    page = app_page
    _open_eligibility(page, studio_url)
    select = page.locator("#smEligCriteriaSelect")
    add = page.locator("#smEligCriteriaAdd")
    expect(select.locator("option:checked")).to_have_text("Add variable…")  # not "Age"
    expect(add).to_be_disabled()
    select.select_option(label="Age")
    expect(add).to_be_enabled()
    add.click()
    expect(page.locator("#smEligCriteriaList [data-i]")).to_have_count(1)
    expect(select.locator("option:checked")).to_have_text("Add variable…")  # reset, Age is not the default again
    expect(add).to_be_disabled()
    select.select_option(label="Other measure")  # still reachable
    add.click()
    expect(page.locator("#smEligCriteriaList [data-i]")).to_have_count(2)


def test_the_criterion_check_turns_green_once_every_field_is_filled(app_page, studio_url):
    page = app_page
    _open_eligibility(page, studio_url)
    page.select_option("#smEligCriteriaSelect", label="Age")
    page.click("#smEligCriteriaAdd")
    row = page.locator("#smEligCriteriaList [data-i]").first
    accept = row.locator('[data-f="accept"]')
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))  # nothing entered yet
    row.locator('[data-f="min"]').fill("5")
    row.locator('[data-f="max"]').fill("20")  # unit "years" is pre-filled: everything is there now
    expect(accept).to_be_enabled()
    expect(accept).to_have_class(re.compile("btn-success"))
    row.locator('[data-f="min"]').fill("")
    row.locator('[data-f="max"]').fill("")
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))
