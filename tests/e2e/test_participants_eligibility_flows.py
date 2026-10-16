"""Converter > Sociodemographics: link a column to an eligibility criterion from the project."""

import json

from playwright.sync_api import expect

from tests.e2e.test_converter_participants_flows import (
    confirm_annotation,
    open_participants_tab,
    select_people_file,
)

AGE = {"id": "age", "label": "Age", "term": "nb:Age", "type": "numeric",
       "mode": "include", "min": 18, "max": 35, "unit": "years"}


def test_mapping_age_preselects_the_criterion_and_saves_only_the_link(app_page, studio_url, tmp_path, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"Criteria": [AGE]}
    (project / "project.json").write_text(json.dumps(meta))
    page = app_page
    open_participants_tab(page, studio_url)
    select_people_file(page, tmp_path)
    page.click("#participantsPreviewBtn")

    page.locator(".nb-column-item", has_text="age").first.click()
    page.select_option("#nb-map-age", "Age")
    page.get_by_role("button", name="Map", exact=True).click()
    expect(page.locator("#nb-elig-age")).to_have_value("age")

    confirm_annotation(page)
    page.click("#participantsConvertBtn")
    expect(page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    sidecar = json.loads((project / "participants.json").read_text())
    assert sidecar["age"]["EligibilityCriterion"] == "age"
    assert "EligibilityCriterion" not in sidecar.get("sex", {})
    assert "min" not in json.dumps(sidecar)  # limits stay in project.json
