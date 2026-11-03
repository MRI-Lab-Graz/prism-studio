"""Projects page: create, open and edit a project the way a user does."""

import json
import re

from playwright.sync_api import expect


def test_create_project_is_blocked_until_required_metadata_is_filled(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my_study")
    bare_page.fill("#projectPath", str(tmp_path))

    # the metadata form opens by itself and Create stays grey until it is complete
    expect(bare_page.locator("#studyMetadataSection")).to_be_visible()
    expect(bare_page.locator("#createProjectSubmitBtnTop")).to_be_disabled()
    expect(bare_page.locator("#createProjectSubmitBtn")).to_be_disabled()
    expect(bare_page.locator("#createProjectSubmitBtnTop")).to_have_attribute("title", re.compile("required"))
    assert not (tmp_path / "my_study").exists()


def test_create_project_works_once_required_metadata_is_filled(bare_page, studio_url, tmp_path, fill_required_metadata):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my_study")
    bare_page.fill("#projectPath", str(tmp_path))
    expect(bare_page.locator("#preliminaryCreateBtnTop")).to_have_count(0)  # no way around the required fields

    fill_required_metadata(bare_page)
    expect(bare_page.locator("#createProjectSubmitBtnTop")).to_be_enabled()
    bare_page.click("#createProjectSubmitBtnTop")

    expect(bare_page.locator("#createResult")).to_contain_text("my_study")
    assert (tmp_path / "my_study" / "project.json").is_file()
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(tmp_path / "my_study")


def test_open_existing_project_makes_it_current_and_remembers_it(bare_page, studio_url, project):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(project))

    bare_page.click("#loadProjectBtn")

    # disabled alone also matches the spinner while loading; the title marks "already loaded"
    expect(bare_page.locator("#loadProjectBtn")).to_have_attribute("title", "This project is already loaded")
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(project)

    bare_page.reload()
    expect(bare_page.locator("#recentProjectsList")).to_contain_text(project.name)


def test_a_loaded_project_opens_its_metadata_and_shows_no_validator_or_datalad_box(bare_page, studio_url, project):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(project))
    bare_page.click("#loadProjectBtn")

    expect(bare_page.locator("#projectBoxSaveBtn")).to_be_visible()
    expect(bare_page.locator("#studyMetadataSection")).to_be_visible()  # opened like for a new project
    expect(bare_page.locator("#smCoreSetupGroupBody")).to_be_visible()
    expect(bare_page.locator(".project-loaded-state")).not_to_contain_text("Open Validator")
    expect(bare_page.locator(".project-loaded-state")).not_to_contain_text("DataLad")


def open_study_metadata(page):
    for target in ("#studyMetadataSection", "#smCoreSetupGroupBody", "#smBasics"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()


def test_study_metadata_edit_is_saved_to_the_project_and_survives_reload(app_page, studio_url, project):
    app_page.goto(f"{studio_url}/projects")
    open_study_metadata(app_page)
    app_page.fill("#metadataName", "Sleep and memory")

    app_page.click("#createProjectSubmitBtn")

    expect(app_page.locator("#metadataSaveStatus")).to_contain_text("aved")
    description = json.loads((project / "dataset_description.json").read_text())
    assert description["Name"] == "Sleep and memory"

    app_page.reload()
    open_study_metadata(app_page)
    expect(app_page.locator("#metadataName")).to_have_value("Sleep and memory")


def test_create_project_rejects_a_name_with_spaces(bare_page, studio_url, tmp_path, fill_required_metadata):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my study")
    bare_page.fill("#projectPath", str(tmp_path))
    fill_required_metadata(bare_page)

    bare_page.click("#createProjectSubmitBtnTop")

    assert list(tmp_path.iterdir()) == []


def test_create_project_never_overwrites_an_existing_folder(bare_page, studio_url, tmp_path, fill_required_metadata):
    existing = tmp_path / "my_study"
    existing.mkdir()
    (existing / "precious.txt").write_text("keep me")
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my_study")
    bare_page.fill("#projectPath", str(tmp_path))
    fill_required_metadata(bare_page)

    bare_page.click("#createProjectSubmitBtnTop")
    bare_page.wait_for_timeout(1500)

    assert (existing / "precious.txt").read_text() == "keep me"
    assert not (existing / "project.json").exists()


def test_open_project_with_a_wrong_path_shows_an_error(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(tmp_path / "does_not_exist"))

    bare_page.click("#loadProjectBtn")

    expect(bare_page.locator("#validationResult")).to_be_visible()
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert not current["path"]


def test_switching_projects_shows_the_new_projects_metadata(app_page, studio_url, project, tmp_path):
    other = tmp_path / "other_study"
    other.mkdir()
    (other / "project.json").write_text(json.dumps({"Basics": {"Name": "Other study"}}))
    (other / "dataset_description.json").write_text(
        json.dumps({"Name": "Other study", "BIDSVersion": "1.10.0"})
    )
    app_page.goto(f"{studio_url}/projects")
    open_study_metadata(app_page)
    app_page.fill("#metadataName", "First study name")

    app_page.request.post(f"{studio_url}/api/projects/current", data={"path": str(other), "name": "other"})
    app_page.reload()
    open_study_metadata(app_page)

    expect(app_page.locator("#metadataName")).to_have_value("Other study")


def test_switching_projects_from_the_recent_list_replaces_the_metadata_form(bare_page, studio_url, project, tmp_path):
    other = tmp_path / "other_study"
    other.mkdir()
    (other / "project.json").write_text(json.dumps({"Basics": {"Name": "Other study"}}))
    (other / "dataset_description.json").write_text(
        json.dumps({"Name": "Other study", "BIDSVersion": "1.10.0"})
    )
    for path in (other, project):  # opening both puts both in the recent list
        bare_page.goto(f"{studio_url}/projects")
        bare_page.click("#card-open")
        bare_page.fill("#existingPath", str(path))
        bare_page.click("#loadProjectBtn")
        expect(bare_page.locator("#projectBoxDeleteBtn")).to_be_visible()
    open_study_metadata(bare_page)
    bare_page.fill("#metadataName", "Unsaved edit of the first project")

    bare_page.click("#projectsDropdown")
    bare_page.locator(f'#projectsRecentList .navbar-recent-project[data-path="{other}"]').click()

    bare_page.wait_for_url("**/projects?preserve_current=1")
    open_study_metadata(bare_page)
    expect(bare_page.locator("#metadataName")).to_have_value("Other study")
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(other)


def test_generate_methods_shows_a_preview_and_offers_a_markdown_download(bare_page, studio_url, project):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(project))
    bare_page.click("#loadProjectBtn")
    expect(bare_page.locator("#methodsSectionCard")).to_be_visible()
    bare_page.locator('[data-bs-target="#methodsSectionBody"]').click()

    bare_page.click("#generateMethodsBtn")

    expect(bare_page.locator("#methodsPreview")).not_to_be_empty()
    expect(bare_page.locator("#methodsError")).to_be_hidden()
    with bare_page.expect_download() as download:
        bare_page.click("#downloadMethodsMdBtn")
    assert download.value.suggested_filename.endswith(".md")


def test_methods_warnings_and_word_tex_bib_downloads(bare_page, studio_url, project):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(project))
    bare_page.click("#loadProjectBtn")
    expect(bare_page.locator("#methodsSectionCard")).to_be_visible()
    bare_page.locator('[data-bs-target="#methodsSectionBody"]').click()
    bare_page.click("#generateMethodsBtn")

    expect(bare_page.locator("#methodsWarnings")).to_contain_text("sample size")
    for button, name in (
        ("#exportMethodsDocxBtn", "methods_section_en.docx"),
        ("#exportMethodsTexBtn", "methods_section_en.tex"),
        ("#exportMethodsBibBtn", "references.bib"),
    ):
        with bare_page.expect_download() as download:
            bare_page.click(button)
        assert download.value.suggested_filename == name


def test_delete_project_needs_the_exact_name_then_removes_the_folder(bare_page, studio_url, project):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(project))
    bare_page.click("#loadProjectBtn")
    bare_page.click("#projectBoxDeleteBtn")  # only shown in the "Project Loaded" panel
    confirm = bare_page.locator("#deleteProjectConfirmBtn")
    expect(confirm).to_be_disabled()

    bare_page.fill("#deleteProjectConfirmInput", "wrong")
    expect(confirm).to_be_disabled()
    assert project.exists()

    bare_page.fill("#deleteProjectConfirmInput", bare_page.inner_text("#deleteProjectModalName").strip())
    expect(confirm).to_be_enabled()
    confirm.click()

    bare_page.wait_for_url("**/projects?**deleted=1**")
    assert not project.exists()
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert not current["path"]



def test_a_grey_create_button_says_which_required_fields_are_missing(bare_page, studio_url, tmp_path, fill_required_metadata):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "grey_study")
    bare_page.fill("#projectPath", str(tmp_path))

    button = bare_page.locator("#createProjectSubmitBtnTop")
    hint = bare_page.locator("#createProjectActionsTop")
    expect(button).to_be_disabled()
    for text in ("required fields", "Dataset Name", "Keywords", "Timepoints"):
        expect(hint).to_contain_text(text)  # beside the button, not only at the end of Study Metadata

    fill_required_metadata(bare_page)
    expect(button).to_be_enabled()
    expect(hint).not_to_contain_text("Dataset Name")


def test_timepoints_is_required_and_saved_with_the_project(bare_page, studio_url, tmp_path, fill_required_metadata):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "long_study")
    bare_page.fill("#projectPath", str(tmp_path))

    fill_required_metadata(bare_page, timepoints="")
    expect(bare_page.locator("#createProjectSubmitBtnTop")).to_be_disabled()  # everything but Timepoints is set
    bare_page.select_option("#smSDTimepoints", "multiple")
    expect(bare_page.locator("#createProjectSubmitBtnTop")).to_be_disabled()  # a new multi-session study says time or content
    bare_page.select_option("#smSDSessionLabels", "time")
    bare_page.click("#createProjectSubmitBtnTop")

    expect(bare_page.locator("#createResult")).to_contain_text("long_study")
    saved = json.loads((tmp_path / "long_study" / "project.json").read_text())
    assert saved["StudyDesign"]["Timepoints"] == "multiple"
    assert saved["StudyDesign"]["SessionLabels"] == "time"


def test_datalad_details_stay_hidden_until_the_switch_is_on(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")

    details = bare_page.locator("#createDataladDetails")
    expect(bare_page.locator('label[for="projectUseDatalad"]')).to_be_visible()  # only the question shows
    expect(details).to_be_hidden()
    expect(bare_page.locator("#createDataladCheckBtn")).to_be_hidden()

    bare_page.click('label[for="projectUseDatalad"]')
    expect(details).to_be_visible()
    expect(bare_page.locator("#createDataladCheckBtn")).to_be_visible()

    bare_page.click('label[for="projectUseDatalad"]')
    expect(details).to_be_hidden()


def test_datalad_setup_check_works_before_any_project_exists(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.click('label[for="projectUseDatalad"]')  # the check is part of the DataLad details

    bare_page.click("#createDataladCheckBtn")

    result = bare_page.locator("#createDataladCheckResult")
    expect(result).to_contain_text("git-annex")
    expect(result).to_contain_text("ssh-key")
    expect(bare_page.locator("#createDataladCheckBtn")).to_be_enabled()
