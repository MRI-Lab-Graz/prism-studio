import json

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

    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()  # required fields still missing
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    saved = json.loads((project / "project.json").read_text())["Eligibility"]["Criteria"]
    assert saved[0] == AGE
    assert saved[1] == {"id": "sex", "label": "Sex", "term": "nb:Sex", "type": "categorical",
                        "mode": "exclude", "values": ["Male"]}
