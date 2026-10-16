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


def test_funding_rows_are_drafts_and_the_empty_placeholder_comes_back(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#metadataFundingYes")
    row = page.locator("#metadataFundingList .funding-row").first
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    row.locator(".funding-agency-input").fill("FWF")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    assert page.input_value("#metadataFunding") == ""  # a draft is not saved
    row.locator('[data-f="accept"]').click()
    assert page.input_value("#metadataFunding") == "FWF"
    row.locator('[data-f="remove"]').click()
    # deleting the last row leaves the empty placeholder draft, nothing saved
    expect(page.locator("#metadataFundingList .funding-row")).to_have_count(1)
    expect(page.locator('#metadataFundingList [data-f="accept"]')).to_have_count(1)
    assert page.input_value("#metadataFunding") == ""


def test_saving_a_loaded_project_without_touching_rows_keeps_authors_and_funding(app_page, studio_url, project):
    description = {"Name": "e2e", "BIDSVersion": "1.10.0",
                   "Authors": ["Ada Lovelace"], "Funding": ["FWF, P12345"]}
    (project / "dataset_description.json").write_text(json.dumps(description))
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    expect(page.locator('#metadataFundingList [data-f="remove"]')).to_have_count(1)  # loaded = defined
    page.click("#createProjectSubmitBtn")
    page.get_by_role("button", name="Save Preliminary State").click()
    expect(page.locator("#metadataSaveStatus")).to_contain_text("aved")
    saved = json.loads((project / "dataset_description.json").read_text())
    assert saved["Funding"] == ["FWF, P12345"]
    assert "Lovelace" in (project / "project.json").read_text()  # authors live in project.json


def test_missing_files_rows_are_drafts_until_accepted(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smReportingFollowupGroupBody", "#smMissingData")
    page.click("#smMissingFilesAddRow")
    row = page.locator("#smMissingFilesList .missing-files-row").last
    expect(row.locator('[data-f="accept"]')).to_be_disabled()
    row.locator(".missing-files-reason").select_option("motion_artifact")
    expect(row.locator('[data-f="accept"]')).to_be_enabled()
    expect(row.locator('[data-f="remove"]')).to_have_count(0)
    assert page.input_value("#smMissingFiles") == ""
    row.locator('[data-f="accept"]').click()
    expect(row.locator('[data-f="remove"]')).to_have_count(1)
    assert "motion_artifact" in page.input_value("#smMissingFiles")


def test_location_picker_add_button_is_the_green_check_and_loaded_locations_are_defined(app_page, studio_url, project):
    meta = json.loads((project / "project.json").read_text())
    meta["Recruitment"] = {"Location": "Graz, Austria"}
    (project / "project.json").write_text(json.dumps(meta))
    open_sections(app_page, studio_url, "#smRecruitmentExecutionGroupBody", "#smRecruitment")
    add = app_page.locator("#recLocationAddBtn")
    expect(add).to_have_class(re.compile("btn-outline-success"))
    expect(add.locator(".fa-check")).to_have_count(1)
    row = app_page.locator("#smRecLocationList .rec-location-row")
    expect(row).to_have_count(1)
    expect(row.locator("button.remove-location")).to_have_count(1)


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
    expect(page.locator("#smRecLocationList .rec-location-row")).to_have_count(1)
    page.click("#createProjectSubmitBtn")
    expect(page.get_by_text("not accepted yet")).to_have_count(0)  # nothing is pending any more
    expect(page.get_by_role("button", name="Save Preliminary State")).to_be_visible()


def test_a_funding_draft_is_not_part_of_the_funding_list(app_page, studio_url):
    page = app_page
    open_sections(page, studio_url, "#smCoreSetupGroupBody")
    page.click("#metadataFundingYes")
    row = page.locator("#metadataFundingList .funding-row").first
    row.locator(".funding-agency-input").fill("FWF")  # typed, not accepted
    listed = page.evaluate(
        "import('/static/js/modules/projects/metadata.js').then(m => m.getFundingList())")
    assert listed == []  # feeds the payload, the draft description and the Core count
    row.locator('[data-f="accept"]').click()
    listed = page.evaluate(
        "import('/static/js/modules/projects/metadata.js').then(m => m.getFundingList())")
    assert listed == ["FWF"]
