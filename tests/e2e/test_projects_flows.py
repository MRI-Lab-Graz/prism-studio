"""Projects page: create, open and edit a project the way a user does."""

import json

from playwright.sync_api import expect


def test_create_project_asks_about_missing_metadata_then_creates_it(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my_study")
    bare_page.fill("#projectPath", str(tmp_path))

    bare_page.click("#createProjectSubmitBtnTop")

    expect(bare_page.get_by_role("heading", name="Required Fields Missing")).to_be_visible()
    assert not (tmp_path / "my_study").exists()  # nothing is written before confirming

    bare_page.get_by_role("button", name="Create anyway (incomplete)").click()

    expect(bare_page.locator("#createResult")).to_contain_text("my_study")
    assert (tmp_path / "my_study" / "project.json").is_file()
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(tmp_path / "my_study")


def test_open_existing_project_makes_it_current_and_remembers_it(bare_page, studio_url, project):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-open")
    bare_page.fill("#existingPath", str(project))

    bare_page.click("#loadProjectBtn")

    expect(bare_page.locator("#loadProjectBtn")).to_be_disabled()  # "already loaded"
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(project)

    bare_page.reload()
    expect(bare_page.locator("#recentProjectsList")).to_contain_text(project.name)


def open_study_metadata(page):
    for target in ("#studyMetadataSection", "#smCoreSetupGroupBody"):
        if not page.locator(target).is_visible():
            page.locator(f'[data-bs-target="{target}"]').click()
            expect(page.locator(target)).to_be_visible()


def test_study_metadata_edit_is_saved_to_the_project_and_survives_reload(app_page, studio_url, project):
    app_page.goto(f"{studio_url}/projects")
    open_study_metadata(app_page)
    app_page.fill("#metadataName", "Sleep and memory")

    app_page.click("#createProjectSubmitBtn")
    app_page.get_by_role("button", name="Save Preliminary State").click()  # required fields still missing

    expect(app_page.locator("#metadataSaveStatus")).to_contain_text("aved")
    description = json.loads((project / "dataset_description.json").read_text())
    assert description["Name"] == "Sleep and memory"

    app_page.reload()
    open_study_metadata(app_page)
    expect(app_page.locator("#metadataName")).to_have_value("Sleep and memory")


def test_create_project_rejects_a_name_with_spaces(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my study")
    bare_page.fill("#projectPath", str(tmp_path))

    bare_page.click("#createProjectSubmitBtnTop")

    expect(bare_page.get_by_role("heading", name="Required Fields Missing")).to_have_count(0)
    assert list(tmp_path.iterdir()) == []


def test_create_project_never_overwrites_an_existing_folder(bare_page, studio_url, tmp_path):
    existing = tmp_path / "my_study"
    existing.mkdir()
    (existing / "precious.txt").write_text("keep me")
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "my_study")
    bare_page.fill("#projectPath", str(tmp_path))

    bare_page.click("#createProjectSubmitBtnTop")
    anyway = bare_page.get_by_role("button", name="Create anyway (incomplete)")
    if anyway.is_visible():
        anyway.click()
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



def test_timepoints_is_required_and_saved_with_the_project(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "long_study")
    bare_page.fill("#projectPath", str(tmp_path))

    bare_page.click("#createProjectSubmitBtnTop")
    expect(bare_page.get_by_role("heading", name="Required Fields Missing")).to_be_visible()
    expect(bare_page.locator(".modal.show")).to_contain_text("Timepoints")
    bare_page.get_by_role("button", name="Go back and fill fields").click()

    open_study_metadata(bare_page)
    bare_page.locator('[data-bs-target="#smStudyDesign"]').click()
    bare_page.select_option("#smSDTimepoints", "multiple")
    bare_page.click("#createProjectSubmitBtnTop")
    bare_page.get_by_role("button", name="Create anyway (incomplete)").click()

    expect(bare_page.locator("#createResult")).to_contain_text("long_study")
    saved = json.loads((tmp_path / "long_study" / "project.json").read_text())
    assert saved["StudyDesign"]["Timepoints"] == "multiple"


def test_datalad_setup_check_works_before_any_project_exists(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")

    bare_page.click("#createDataladCheckBtn")

    result = bare_page.locator("#createDataladCheckResult")
    expect(result).to_contain_text("git-annex")
    expect(result).to_contain_text("ssh-key")
    expect(bare_page.locator("#createDataladCheckBtn")).to_be_enabled()
