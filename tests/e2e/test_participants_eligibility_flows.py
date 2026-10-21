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


def test_mapping_age_leaves_the_criterion_to_the_user_and_saves_only_the_link(app_page, studio_url, tmp_path, project):
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
    expect(page.locator("#nb-elig-age")).to_have_value("")  # never pre-selected, even for Age
    page.select_option("#nb-elig-age", "age")

    confirm_annotation(page)
    page.click("#participantsConvertBtn")
    expect(page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    sidecar = json.loads((project / "participants.json").read_text())
    assert sidecar["age"]["EligibilityCriterion"] == "age"
    assert "EligibilityCriterion" not in sidecar.get("sex", {})
    assert "min" not in json.dumps(sidecar)  # limits stay in project.json


def test_merge_into_existing_files_also_offers_the_criterion(app_page, studio_url, tmp_path, project):
    from tests.e2e.test_converter_participants_flows import start_merge

    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"Criteria": [AGE]}
    (project / "project.json").write_text(json.dumps(meta))
    start_merge(app_page, studio_url, project, tmp_path, "participant_id,age\nP003,50\n")
    app_page.locator(".nb-column-item", has_text="age").first.click()
    expect(app_page.locator("#nb-elig-age")).to_be_visible()


def test_annotating_existing_files_without_a_preview_offers_the_criterion(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"Criteria": [AGE]}
    (project / "project.json").write_text(json.dumps(meta))
    (project / "participants.tsv").write_text("participant_id\tage\nsub-P001\t21\n")
    (project / "participants.json").write_text(json.dumps({"age": {"Description": "Age", "Unit": "years"}}))
    open_participants_tab(app_page, studio_url)
    app_page.evaluate("bootstrap.Collapse.getOrCreateInstance(document.getElementById('neurobagelCollapse')).show(); loadNeurobagelWidget()")
    app_page.locator(".nb-column-item", has_text="age").first.click()
    expect(app_page.locator("#nb-elig-age")).to_be_visible()


def test_modify_existing_files_offers_the_criterion(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"Criteria": [AGE]}
    (project / "project.json").write_text(json.dumps(meta))
    (project / "participants.tsv").write_text("participant_id\tage\nsub-P001\t21\n")
    (project / "participants.json").write_text(json.dumps({"age": {"Description": "Age", "Unit": "years"}}))
    app_page.on("dialog", lambda dialog: dialog.accept())
    open_participants_tab(app_page, studio_url)
    app_page.click('[data-participants-case-id="2"]')  # Modify the existing files
    app_page.click("#participantsPreviewBtn")
    app_page.locator(".nb-column-item", has_text="age").first.click()
    expect(app_page.locator("#nb-elig-age")).to_be_visible()


def test_an_unchosen_criterion_is_not_saved(app_page, studio_url, tmp_path, project):
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
    confirm_annotation(page)
    page.click("#participantsConvertBtn")
    expect(page.locator("#participantsSuccess")).to_be_visible(timeout=30000)
    assert "EligibilityCriterion" not in json.loads((project / "participants.json").read_text())["age"]
