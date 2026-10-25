"""Projects page: every add-a-row control is a draft (green check, Cancel) until accepted;
the red cross only appears on defined rows."""

import json
import re

import pytest
from playwright.sync_api import expect


@pytest.fixture(autouse=True)
def _no_authors_yet(project):
    """The shared project is complete (it has an author); these tests start with an empty author list."""
    meta = json.loads((project / "project.json").read_text())
    del meta["Basics"]["Authors"]
    (project / "project.json").write_text(json.dumps(meta))


def open_sections(page, studio_url, *targets):
    page.goto(f"{studio_url}/projects")
    for target in ("#studyMetadataSection", *targets):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()








def test_an_accepted_doi_becomes_a_chip(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smReferences")
    box = page.locator("#smReferencesList")
    box.locator(".chip-input").fill("10.1000/xyz123")
    expect(box.locator('[data-f="accept"]')).to_be_enabled()
    box.locator('[data-f="accept"]').click()
    expect(box.locator(".chip-badge")).to_have_count(1)
    assert "10.1000/xyz123" in page.input_value("#smReferencesText")


def test_a_malformed_doi_cannot_be_accepted(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smReferences")
    box = page.locator("#smReferencesList")
    box.locator(".chip-input").fill("not a doi")
    expect(box.locator('[data-f="accept"]')).to_be_disabled()


def test_a_new_author_is_a_draft_that_counts_only_after_it_is_accepted(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    row = page.locator("#metadataAuthorsList .author-row").first
    badge = page.locator("#metadataAuthorsRequiredBadge")

    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    row.locator(".author-first").fill("Ada")
    expect(row.locator('[data-f="accept"]')).to_be_disabled()  # last name missing
    row.locator(".author-last").fill("Lovelace")
    row.locator(".author-corresponding").check()
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    expect(row.locator('[data-f="remove"]')).to_have_count(0)
    expect(badge).not_to_have_class(re.compile("bg-success"))  # a draft is not an author yet

    row.locator('[data-f="accept"]').click()
    expect(row.locator('[data-f="remove"]')).to_have_count(1)
    expect(badge).to_have_class(re.compile("bg-success"))

    page.click("#addAuthorRow")
    second = page.locator("#metadataAuthorsList .author-row").nth(1)
    second.locator(".author-first").fill("Grace")  # half-filled draft must not turn the badge red
    expect(badge).to_have_class(re.compile("bg-success"))
    second.locator('[data-f="cancel"]').click()
    expect(page.locator("#metadataAuthorsList .author-row")).to_have_count(1)


def test_loaded_authors_are_defined(app_page, studio_url, project):
    (project / "dataset_description.json").write_text(
        json.dumps({"Name": "e2e", "BIDSVersion": "1.10.0", "Authors": ["Ada Lovelace"]}))
    open_sections(app_page, studio_url, "#smCoreSetupGroupBody")
    row = app_page.locator("#metadataAuthorsList .author-row").first
    expect(row.locator(".author-last")).to_have_value("Lovelace")
    expect(row.locator('[data-f="remove"]')).to_have_count(1)
    expect(row.locator('[data-f="accept"]')).to_have_count(0)




def test_saving_a_loaded_project_without_touching_rows_keeps_authors_and_funding(app_page, studio_url, project):
    description = {"Name": "e2e", "BIDSVersion": "1.10.0",
                   "Authors": ["Ada Lovelace"], "Funding": ["FWF, P12345"]}
    (project / "dataset_description.json").write_text(json.dumps(description))
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    expect(page.locator("#metadataFundingList .chip-badge")).to_have_count(1)  # loaded = a chip
    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    saved = json.loads((project / "dataset_description.json").read_text())
    assert saved["Funding"] == ["FWF, P12345"]
    assert "Lovelace" in (project / "project.json").read_text()  # authors live in project.json




def test_location_picker_add_button_is_the_green_check_and_loaded_locations_are_chips(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Recruitment"] = {"Location": "Graz, Austria"}
    (project / "project.json").write_text(json.dumps(meta))
    open_sections(app_page, studio_url, "#smRecruitmentExecutionGroupBody", "#smRecruitment")
    add = app_page.locator("#recLocationAddBtn")
    expect(add).to_have_class(re.compile("btn-outline-success"))
    expect(add.locator(".fa-check")).to_have_count(1)
    chip = app_page.locator("#smRecLocationList .chip-badge")
    expect(chip).to_have_count(1)
    expect(chip.first).to_contain_text("Graz, Austria")
    expect(chip.first).to_have_class(re.compile("btn-outline-primary"))  # a green chip, no red cross


def _project_json_text(project):
    return (project / "project.json").read_text()


def _fill_draft_author(page):
    row = page.locator("#metadataAuthorsList .author-row").first
    row.locator(".author-first").fill("Ada")
    row.locator(".author-last").fill("Lovelace")
    return row


def test_saving_is_blocked_while_a_draft_with_content_is_pending(app_page, studio_url, project):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    before = _project_json_text(project)
    row = _fill_draft_author(page)  # typed, not accepted

    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_be_visible()
    expect(row).to_have_class(re.compile("row-pending"))
    expect(page.get_by_role("button", name="Save Preliminary State")).to_have_count(0)  # no save flow started
    assert _project_json_text(project) == before  # nothing was sent

    row.locator('[data-f="accept"]').click()
    expect(row).not_to_have_class(re.compile("row-pending"))
    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()  # now the normal flow runs
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    assert "Lovelace" in _project_json_text(project)


def test_an_empty_draft_does_not_block_saving(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#addAuthorRow")  # an empty draft next to the empty placeholder
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_role("button", name="Save Preliminary State")).to_be_visible()  # normal flow
    expect(page.get_by_text("not accepted yet")).to_have_count(0)


def test_text_typed_into_the_location_search_blocks_saving_but_an_empty_search_does_not(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smRecruitment")
    page.fill("#recLocationQuery", "Graz")
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_be_visible()
    expect(page.locator("#recLocationPickerGroup")).to_have_class(re.compile("row-pending"))
    page.fill("#recLocationQuery", "")
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_role("button", name="Save Preliminary State")).to_be_visible()


def test_creating_a_new_project_is_blocked_while_a_draft_is_pending(bare_page, studio_url, tmp_path):
    page = bare_page
    page.goto(f"{studio_url}/projects")
    page.click("#card-create")
    page.fill("#projectName", "row_guard_study")
    page.fill("#projectPath", str(tmp_path))
    for target in ("#studyMetadataSection", "#smCoreSetupGroupBody"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()
    row = _fill_draft_author(page)
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_be_visible()
    expect(row).to_have_class(re.compile("row-pending"))
    assert not (tmp_path / "row_guard_study").exists()  # nothing was created


def test_a_project_switch_clears_a_half_typed_location_search(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smRecruitment")
    page.fill("#recLocationQuery", "Graz")
    page.evaluate("window.dispatchEvent(new Event('prism-project-changed'))")
    expect(page.locator("#recLocationQuery")).to_have_value("")
    page.click("#createProjectSubmitBtn")  # must not be blocked by the previous project's typing
    expect(page.get_by_text("not accepted yet")).to_have_count(0)


def test_after_searching_and_adding_a_location_saving_is_not_blocked(app_page, studio_url):
    page = app_page
    page.route("**/api/projects/recruitment-location-search*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"results": [{"display_name": "Graz, Styria, Austria"}]})))
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smRecruitment")
    page.fill("#recLocationQuery", "Graz")
    page.click("#recLocationSearchBtn")
    expect(page.locator("#recLocationResultsRow")).to_be_visible()
    page.click("#recLocationAddBtn")
    expect(page.locator("#smRecLocationList .chip-badge")).to_have_count(1)
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_have_count(0)  # nothing is pending any more
    expect(page.get_by_role("button", name="Save Preliminary State")).to_be_visible()




def test_a_pending_draft_triggers_the_unsaved_changes_warning_when_leaving_the_project(app_page, studio_url):
    page = app_page
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    page.wait_for_timeout(1500)  # let the project's metadata finish loading
    page.locator("#smEligInclusionList .chip-input").fill("Adults")  # typed, not accepted
    page.click("#card-create")
    page.wait_for_timeout(500)
    assert any("unsaved" in message.lower() for message in dialogs), dialogs


def test_an_added_checked_criterion_is_an_unsaved_change(app_page, studio_url):
    page = app_page
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    page.wait_for_timeout(1500)
    page.select_option("#smEligCriteriaSelect", label="Age")
    page.click("#smEligCriteriaAdd")
    row = page.locator("#smEligCriteriaList [data-i]").first
    row.locator('[data-f="min"]').fill("18")
    row.locator('[data-f="accept"]').click()
    page.click("#card-create")
    page.wait_for_timeout(500)
    assert any("unsaved" in message.lower() for message in dialogs), dialogs


def test_the_orcid_helper_filling_the_names_enables_the_check(app_page, studio_url):
    page = app_page
    page.route("**/api/projects/orcid/search*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"success": True, "candidates": [{
            "orcid_id": "0000-0002-1825-0097", "given_names": "Ada", "family_name": "Lovelace",
            "affiliation": "Analytical Engines"}]})))
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    row = page.locator("#metadataAuthorsList .author-row").first
    row.locator(".author-last").fill("Lovelace")  # first name missing: the check is disabled
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    row.locator(".author-orcid-find").click()  # one candidate: picked without a dialog
    expect(row.locator(".author-first")).to_have_value("Ada")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()  # the helper filled what was missing


def test_accepting_an_author_searches_the_orcid_when_it_is_empty(app_page, studio_url):
    page = app_page
    page.route("**/api/projects/orcid/search*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"success": True, "candidates": [{
            "orcid_id": "0000-0002-1825-0097", "orcid": "https://orcid.org/0000-0002-1825-0097",
            "given_names": "Ada", "family_name": "Lovelace", "affiliation": "Analytical Engines"}]})))
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    row = page.locator("#metadataAuthorsList .author-row").first
    row.locator(".author-first").fill("Ada")
    row.locator(".author-last").fill("Lovelace")
    expect(row.locator(".author-orcid")).to_have_value("")  # typing the names alone searches nothing
    row.locator('[data-f="accept"]').click()
    expect(row.locator(".author-orcid")).to_have_value(re.compile("0000-0002-1825-0097"))


def test_new_project_starts_without_the_previous_projects_criteria(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"Criteria": [{"id": "age", "label": "Age", "term": "nb:Age", "type": "numeric",
                                         "mode": "include", "min": 18, "max": 35, "unit": "years"}]}
    (project / "project.json").write_text(json.dumps(meta))
    page = app_page
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    expect(page.locator("#smEligCriteriaList .chip-badge")).to_have_count(1)
    page.click("#card-create")
    expect(page.locator("#smEligCriteriaList .chip-badge")).to_have_count(0)
    expect(page.locator("#smEligCriteriaRequiredBadge")).not_to_have_class(re.compile("bg-success"))


def test_a_disabled_check_says_what_is_missing(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    row = page.locator("#metadataAuthorsList .author-row").first
    expect(row.locator('[data-f="hint"]')).to_contain_text("first and last name")
    row.locator(".author-first").fill("Ada")
    row.locator(".author-last").fill("Lovelace")
    expect(row.locator('[data-f="hint"]')).to_have_count(0)  # complete: nothing missing
    expect(row.locator('[data-f="accept"]')).to_be_enabled()


def test_the_check_is_gray_until_the_row_is_complete_and_then_turns_green(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    row = page.locator("#metadataAuthorsList .author-row").first
    accept = row.locator('[data-f="accept"]')
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))  # nothing set: nothing looks ok
    expect(accept).not_to_have_class(re.compile("btn-success|btn-outline-success"))
    row.locator(".author-first").fill("Ada")
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))  # still incomplete
    row.locator(".author-last").fill("Lovelace")
    expect(accept).to_have_class(re.compile("btn-success"))
    row.locator(".author-last").fill("")
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))  # back to gray when emptied


def test_overview_placeholders_state_variables_instead_of_comparing_them(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody", "#smOverview")
    placeholder = page.locator("#smOverviewIVList .chip-input").get_attribute("placeholder")
    assert placeholder.startswith("e.g.,")
    assert " vs" not in placeholder  # an independent variable is named, not compared


# ---- list fields: one input, accepted entries become green chips below (like the CRediT roles) ----

def _open_overview(page, studio_url):
    open_sections(page, studio_url, "#smCoreSetupGroupBody", "#smOverview")


def test_a_list_field_turns_accepted_entries_into_green_chips_below_one_input(app_page, studio_url):
    page = app_page
    _open_overview(page, studio_url)
    field = page.locator("#smOverviewIVList")
    typed = field.locator(".chip-input")
    accept = field.locator('[data-f="accept"]')
    chips = field.locator(".chip-badge")

    expect(accept).to_be_disabled()  # nothing typed
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))
    typed.fill("stimulus valence")
    expect(accept).to_have_class(re.compile("btn-success"))
    assert page.input_value("#smOverviewIV") == ""  # typed, not accepted: not part of the form yet

    accept.click()
    expect(chips).to_have_count(1)
    expect(chips.first).to_contain_text("stimulus valence")
    expect(chips.first).to_have_class(re.compile("btn-outline-primary"))  # the CRediT chip look
    expect(typed).to_have_value("")  # ready for the next entry
    expect(accept).to_be_disabled()
    assert page.input_value("#smOverviewIV") == "stimulus valence"

    typed.fill("task difficulty")
    typed.press("Enter")  # Enter accepts as well
    expect(chips).to_have_count(2)
    assert page.input_value("#smOverviewIV") == "stimulus valence\ntask difficulty"

    chips.first.click()  # clicking a chip removes it
    expect(chips).to_have_count(1)
    assert page.input_value("#smOverviewIV") == "task difficulty"


def test_a_duplicate_entry_is_not_added_twice(app_page, studio_url):
    page = app_page
    _open_overview(page, studio_url)
    field = page.locator("#smOverviewCVList")
    for text in ("age", "Age"):
        field.locator(".chip-input").fill(text)
        field.locator(".chip-input").press("Enter")
    expect(field.locator(".chip-badge")).to_have_count(1)


def test_loaded_list_values_show_as_chips_and_count_towards_core(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Eligibility"] = {"InclusionCriteria": ["Adults", "Healthy"]}
    (project / "project.json").write_text(json.dumps(meta))
    open_sections(app_page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    chips = app_page.locator("#smEligInclusionList .chip-badge")
    expect(chips).to_have_count(2)
    expect(app_page.locator("#smEligCriteriaRequiredBadge")).to_have_class(re.compile("bg-success"))
    assert app_page.input_value("#smEligInclusion") == "Adults\nHealthy"


def test_text_typed_but_not_accepted_in_a_list_field_blocks_saving(app_page, studio_url, project):
    page = app_page
    _open_overview(page, studio_url)
    before = _project_json_text(project)
    page.locator("#smOverviewDVList .chip-input").fill("reaction times")
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_be_visible()
    assert _project_json_text(project) == before
    page.locator("#smOverviewDVList .chip-input").press("Enter")  # accepted: the chip is part of the form
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_role("button", name="Save Preliminary State")).to_be_visible()



# ---- funding: agency + grant inputs, accepted sources become chips ----

def test_funding_sources_become_chips_below_the_agency_and_grant_inputs(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#metadataFundingYes")
    field = page.locator("#metadataFundingList")
    agency = field.locator(".funding-agency-input")
    grant = field.locator(".funding-grant-input")
    accept = field.locator('[data-f="accept"]')
    chips = field.locator(".chip-badge")

    expect(accept).to_be_disabled()
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))
    grant.fill("P12345")  # a grant without an agency is not enough
    expect(accept).to_be_disabled()
    agency.fill("FWF")
    expect(accept).to_have_class(re.compile("btn-success"))
    assert page.input_value("#metadataFunding") == ""  # typed, not accepted

    accept.click()
    expect(chips).to_have_count(1)
    expect(chips.first).to_contain_text("FWF, P12345")
    expect(agency).to_have_value("")
    expect(grant).to_have_value("")
    assert page.input_value("#metadataFunding") == "FWF, P12345"

    agency.fill("ERC")
    agency.press("Enter")  # Enter accepts, the grant stays optional
    expect(chips).to_have_count(2)
    assert page.input_value("#metadataFunding") == "FWF, P12345\nERC"
    chips.first.click()
    assert page.input_value("#metadataFunding") == "ERC"


def test_a_funding_entry_that_is_typed_but_not_accepted_blocks_saving_and_is_not_listed(app_page, studio_url, project):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#metadataFundingYes")
    before = _project_json_text(project)
    page.locator("#metadataFundingList .funding-agency-input").fill("FWF")
    badge = page.locator("#metadataFundingRequiredBadge")
    expect(badge).not_to_have_class(re.compile("bg-success"))  # a typed source is not funding yet
    assert page.input_value("#metadataFunding") == ""
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_be_visible()
    assert _project_json_text(project) == before


def test_accepting_a_funding_source_turns_the_funding_badge_green(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#metadataFundingYes")
    field = page.locator("#metadataFundingList")
    field.locator(".funding-agency-input").fill("FWF")
    field.locator(".funding-agency-input").press("Enter")
    expect(page.locator("#metadataFundingRequiredBadge")).to_have_class(re.compile("bg-success"))



# ---- known issues: two inputs, accepted entries become chips ----

def test_known_issues_become_chips_with_the_file_and_the_issue(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smMissingData")
    field = page.locator("#smKnownIssuesList")
    first, second = field.locator(".two-field-input-1"), field.locator(".two-field-input-2")
    accept = field.locator('[data-f="accept"]')
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))
    first.fill("sub-002_task-nback_bold.nii")
    expect(accept).to_have_class(re.compile("btn-success"))  # one field is enough
    assert page.input_value("#smKnownIssues") == ""
    second.fill("Shorter scan")
    accept.click()
    chip = field.locator(".chip-badge")
    expect(chip).to_have_count(1)
    expect(chip.first).to_contain_text("sub-002_task-nback_bold.nii – Shorter scan")
    assert page.input_value("#smKnownIssues") == "sub-002_task-nback_bold.nii | Shorter scan"
    expect(first).to_have_value("")
    chip.first.click()
    assert page.input_value("#smKnownIssues") == ""



# ---- missing files: subject/session/modality/reason/detail, accepted entries become chips ----

def test_missing_files_entries_become_chips_with_a_readable_summary(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smMissingData")
    field = page.locator("#smMissingFilesList")
    accept = field.locator('[data-f="accept"]')
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))  # nothing chosen yet
    field.locator(".missing-files-reason").select_option("motion_artifact")
    expect(accept).to_have_class(re.compile("btn-success"))
    field.locator(".missing-files-detail").fill("excessive movement")
    assert page.input_value("#smMissingFiles") == ""  # chosen, not accepted
    accept.click()
    chip = field.locator(".chip-badge")
    expect(chip).to_have_count(1)
    expect(chip.first).to_contain_text("Motion artifact (excessive movement)")
    assert "motion_artifact" in page.input_value("#smMissingFiles")
    expect(field.locator(".missing-files-reason")).to_have_value("")  # the entry row is ready again
    expect(accept).to_have_class(re.compile("btn-outline-secondary"))
    chip.first.click()
    assert page.input_value("#smMissingFiles") == ""


def test_an_added_location_is_a_chip_that_can_be_removed_and_counts_for_the_location_badge(app_page, studio_url):
    page = app_page
    page.route("**/api/projects/recruitment-location-search*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"results": [{"display_name": "Graz, Styria, Austria"}]})))
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smRecruitment")
    badge = page.locator("#smRecLocationRequiredBadge")
    expect(badge).not_to_have_class(re.compile("bg-success"))
    page.fill("#recLocationQuery", "Graz")
    page.click("#recLocationSearchBtn")
    page.click("#recLocationAddBtn")
    chip = page.locator("#smRecLocationList .chip-badge")
    expect(chip).to_have_count(1)
    expect(chip.first).to_contain_text("Graz, Styria, Austria")
    expect(badge).to_have_class(re.compile("bg-success"))
    chip.first.click()
    expect(chip).to_have_count(0)
    expect(badge).not_to_have_class(re.compile("bg-success"))


def test_an_author_who_is_already_listed_cannot_be_added_twice(app_page, studio_url, project):
    (project / "dataset_description.json").write_text(
        json.dumps({"Name": "e2e", "BIDSVersion": "1.10.0", "Authors": ["Ada Lovelace"]}))
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#addAuthorRow")
    row = page.locator("#metadataAuthorsList .author-row").nth(1)
    row.locator(".author-first").fill("ada")
    row.locator(".author-last").fill("LOVELACE")
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    row.locator(".author-first").fill("Grace")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()


def test_a_criterion_with_min_above_max_cannot_be_accepted(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smRecruitmentExecutionGroupBody", "#smEligibility")
    page.select_option("#smEligCriteriaSelect", label="Age")
    page.click("#smEligCriteriaAdd")
    draft = page.locator("#smEligCriteriaList [data-i]")
    draft.locator('[data-f="min"]').fill("35")
    draft.locator('[data-f="max"]').fill("18")
    expect(draft.locator('[data-f="accept"]')).to_be_disabled()
    draft.locator('[data-f="max"]').fill("40")
    expect(draft.locator('[data-f="accept"]')).to_be_enabled()
