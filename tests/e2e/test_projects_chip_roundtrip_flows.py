"""Chip lists: what was stored loads and saves unchanged, and nothing leaks between projects."""

import json
import re

from playwright.sync_api import expect


def _open(page, studio_url, *targets):
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", *targets):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()


def _edit_project(project, **sections):
    meta = json.loads((project / "project.json").read_text())
    for name, value in sections.items():
        meta.setdefault(name, {}).update(value)
    (project / "project.json").write_text(json.dumps(meta))


def test_new_project_starts_without_known_issues_and_missing_files_of_the_previous_project(app_page, studio_url, project):
    _edit_project(project, MissingData={"KnownIssues": "f.nii | bad", "MissingFiles": "sub-01 |  |  | other"})
    page = app_page
    _open(page, studio_url)
    expect(page.locator("#smKnownIssuesList .chip-badge")).to_have_count(1)
    expect(page.locator("#smMissingFilesList .chip-badge")).to_have_count(1)
    page.click("#card-create")
    expect(page.locator("#smKnownIssuesList .chip-badge")).to_have_count(0)
    expect(page.locator("#smMissingFilesList .chip-badge")).to_have_count(0)


def test_untouched_lists_are_saved_exactly_as_they_were_loaded(app_page, studio_url, project):
    independent = ["Age", "age", "a  b", "x | y"]  # case variants, a double space, a pipe: all legitimate
    inclusion = ["Adults  18+", "adults 18+"]
    funding = ["FWF, P1, extra", "fwf, p1, extra", "NIH  R01"]
    _edit_project(project, Overview={"IndependentVariables": independent}, Eligibility={"InclusionCriteria": inclusion})
    (project / "dataset_description.json").write_text(json.dumps(
        {"Name": "e2e", "BIDSVersion": "1.10.0", "Funding": funding}))
    page = app_page
    _open(page, studio_url)
    page.wait_for_timeout(1500)
    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    saved = json.loads((project / "project.json").read_text())
    assert saved["Overview"]["IndependentVariables"] == independent
    assert saved["Eligibility"]["InclusionCriteria"] == inclusion
    assert json.loads((project / "dataset_description.json").read_text())["Funding"] == funding


def test_criteria_with_odd_ids_load_and_each_chip_removes_only_itself(app_page, studio_url, project):
    def crit(cid, label):
        return {"id": cid, "label": label, "term": None, "type": "numeric", "mode": "include", "min": 1}
    _edit_project(project, Eligibility={"Criteria": [crit("iq ", "IQ"), crit("my  crit", "Mine"),
                                                     crit("Dup", "Upper"), crit("dup", "Lower")]},
                  Procedure={"Overview": "the load reached this field"})
    page = app_page
    _open(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    chips = page.locator("#smEligCriteriaList .chip-badge")
    expect(chips).to_have_count(4)
    assert "the load reached this field" in page.evaluate("document.getElementById('smProcOverview').value")
    chips.first.click()
    expect(chips).to_have_count(3)  # only the one that was clicked
    expect(page.locator("#smEligCriteriaList")).to_contain_text("Upper")
    expect(page.locator("#smEligCriteriaList")).to_contain_text("Lower")


def test_dataset_description_messages_cannot_inject_html(app_page, studio_url, project):
    (project / "dataset_description.json").write_text(json.dumps({
        "Name": "e2e", "BIDSVersion": "1.10.0",
        "Keywords": '<img src=x id=pwned onerror="window.__pwned=1">'}))
    page = app_page
    _open(page, studio_url, "#smCoreSetupGroupBody")
    expect(page.locator("#metadataValidationFeedback")).to_be_visible()
    page.wait_for_timeout(800)
    assert page.evaluate("window.__pwned") is None
    expect(page.locator("#pwned")).to_have_count(0)


def test_a_loaded_incomplete_criterion_is_kept_as_a_draft_and_blocks_saving_with_a_clear_message(app_page, studio_url, project):
    _edit_project(project, Eligibility={"Criteria": [
        {"id": "hand", "label": "Handedness", "term": "nb:Handedness", "type": "categorical", "mode": "include"}]})
    page = app_page
    _open(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    expect(page.locator("#smEligCriteriaList [data-i]")).to_have_count(1)  # not silently dropped
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_be_visible()


def test_removing_and_re_adding_a_criterion_keeps_its_hand_written_id(app_page, studio_url, project):
    _edit_project(project, Eligibility={"Criteria": [
        {"id": "min_age", "label": "Age", "term": "nb:Age", "type": "numeric", "mode": "include", "min": 18, "unit": "years"}]})
    page = app_page
    _open(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    chips = page.locator("#smEligCriteriaList .chip-badge")
    expect(chips).to_have_count(1)
    chips.first.click()  # remove ...
    expect(chips).to_have_count(0)
    page.select_option("#smEligCriteriaSelect", label="Age")  # ... and add the same criterion again
    page.click("#smEligCriteriaAdd")
    draft = page.locator("#smEligCriteriaList [data-i]")
    draft.locator('[data-f="min"]').fill("21")
    draft.locator('[data-f="accept"]').click()
    expect(chips).to_have_count(1)
    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    saved = json.loads((project / "project.json").read_text())["Eligibility"]["Criteria"]
    assert [c["id"] for c in saved] == ["min_age"]  # participants.json links to it keep working
    assert saved[0]["min"] == 21
