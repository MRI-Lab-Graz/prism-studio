"""JSON editor: open a project file, edit it, save it back."""

import json
import re

from playwright.sync_api import expect


def open_project_file(page, studio_url, name):
    page.goto(f"{studio_url}/editor/?autoload={name}&from=project")


def alerts(page):
    return page.locator("#alertContainer").inner_text()


def set_text(page, data):
    page.locator("#jsonEditor").fill(data if isinstance(data, str) else json.dumps(data, indent=2))


def test_a_project_file_opens_ready_to_edit(app_page, studio_url, project):
    open_project_file(app_page, studio_url, "dataset_description")

    expect(app_page.locator("#jsonEditor")).to_be_visible()
    shown = json.loads(app_page.locator("#jsonEditor").input_value())
    assert shown == json.loads((project / "dataset_description.json").read_text())
    expect(app_page.locator("#editorFileName")).to_have_text("dataset_description.json")


def test_saving_writes_the_edit_to_the_project_file(app_page, studio_url, project):
    open_project_file(app_page, studio_url, "dataset_description")
    expect(app_page.locator("#jsonEditor")).to_be_visible()
    data = json.loads(app_page.locator("#jsonEditor").input_value())
    data["Name"] = "Renamed in the editor"
    set_text(app_page, data)

    app_page.click("#saveToProjectBtn")

    expect(app_page.locator("#alertContainer")).to_contain_text("Saved dataset_description.json")
    assert json.loads((project / "dataset_description.json").read_text())["Name"] == "Renamed in the editor"


def test_saved_file_with_gaps_warns_what_is_missing(app_page, studio_url):
    open_project_file(app_page, studio_url, "dataset_description")
    expect(app_page.locator("#jsonEditor")).to_be_visible()

    app_page.click("#saveToProjectBtn")

    expect(app_page.locator("#alertContainer")).to_contain_text("validation found issues")
    for field in ("Authors", "Keywords", "DatasetType"):  # what the Validate page would also flag
        assert field in alerts(app_page)


def test_broken_json_is_refused_and_the_file_stays_as_it_was(app_page, studio_url, project):
    before = (project / "dataset_description.json").read_text()
    open_project_file(app_page, studio_url, "dataset_description")
    expect(app_page.locator("#jsonEditor")).to_be_visible()
    set_text(app_page, '{"Name": "oops",')

    app_page.click("#saveToProjectBtn")

    expect(app_page.locator("#alertContainer .alert-danger")).to_be_visible()
    assert "Error:" in alerts(app_page)
    assert (project / "dataset_description.json").read_text() == before


def test_download_copy_gives_the_edit_and_leaves_the_project_alone(app_page, studio_url, project, tmp_path):
    before = (project / "dataset_description.json").read_text()
    open_project_file(app_page, studio_url, "dataset_description")
    expect(app_page.locator("#jsonEditor")).to_be_visible()
    data = json.loads(app_page.locator("#jsonEditor").input_value())
    data["Name"] = "Copy only"
    set_text(app_page, data)

    with app_page.expect_download() as info:
        app_page.click("#saveBtn")
    target = tmp_path / "copy.json"
    info.value.save_as(target)

    assert info.value.suggested_filename == "dataset_description.json"
    assert json.loads(target.read_text())["Name"] == "Copy only"
    assert (project / "dataset_description.json").read_text() == before


def test_a_file_the_project_does_not_have_says_so(app_page, studio_url):
    app_page.allowed_http[404] = "/editor/api/file/participants"
    open_project_file(app_page, studio_url, "participants")

    expect(app_page.locator("#alertContainer")).to_contain_text("not found")


PARTICIPANTS = {"age": {"Description": "Age in years", "Units": "years"}, "sex": {"Description": "Sex"}}


def test_participants_json_opens_as_a_form_and_saves_the_edited_value(app_page, studio_url, project):
    (project / "participants.json").write_text(json.dumps(PARTICIPANTS))
    open_project_file(app_page, studio_url, "participants")
    field = app_page.locator("[data-json-path='age.Description']")
    expect(field).to_be_visible()
    expect(field).to_have_value("Age in years")
    field.fill("Age at first visit")

    app_page.click("#saveToProjectBtn")

    expect(app_page.locator("#alertContainer")).to_contain_text("Saved participants.json")
    assert "validation found issues" not in alerts(app_page)
    saved = json.loads((project / "participants.json").read_text())
    assert saved["age"]["Description"] == "Age at first visit"
    assert saved["age"]["Units"] == "years" and saved["sex"] == {"Description": "Sex"}


def test_create_new_starts_with_an_empty_object_and_nothing_on_disk(app_page, studio_url, project):
    before = sorted(p.name for p in project.iterdir())
    app_page.goto(f"{studio_url}/editor/")

    app_page.click("#newJsonBtn")

    expect(app_page.locator("#editorFileName")).to_have_text("untitled.json")
    assert json.loads(app_page.locator("#jsonEditor").input_value()) == {}
    assert sorted(p.name for p in project.iterdir()) == before


def test_open_a_json_file_from_disk_with_the_file_chooser(app_page, studio_url, tmp_path):
    other = tmp_path / "task-rest_beh.json"
    other.write_text(json.dumps({"TaskName": "rest"}))
    app_page.goto(f"{studio_url}/editor/")

    app_page.locator("#jsonFileInput").set_input_files(other)

    expect(app_page.locator("#editorFileName")).to_have_text("task-rest_beh.json")
    assert json.loads(app_page.locator("#jsonEditor").input_value()) == {"TaskName": "rest"}


def test_a_file_that_is_not_json_is_refused_with_a_message(app_page, studio_url, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    app_page.goto(f"{studio_url}/editor/")

    app_page.locator("#jsonFileInput").set_input_files(bad)

    expect(app_page.locator("#alertContainer")).to_contain_text("Invalid JSON file")
    expect(app_page.locator("#editorSection")).to_be_hidden()


def pretend_picker(page, endpoint, path):
    """Answer the native picker endpoint ourselves, so no real dialog opens on the dev machine."""
    page.route(f"**/api/{endpoint}*", lambda route: route.fulfill(json={"path": path}))


def test_open_button_opens_the_file_the_picker_returns(app_page, studio_url, tmp_path):
    chosen = tmp_path / "sub-01_task-rest_beh.json"
    chosen.write_text(json.dumps({"TaskName": "rest", "Units": "ms"}))
    pretend_picker(app_page, "browse-file", str(chosen))
    app_page.goto(f"{studio_url}/editor/")

    app_page.click("#jsonFileBtn")

    expect(app_page.locator("#editorFileName")).to_have_text(chosen.name)
    assert json.loads(app_page.locator("#jsonEditor").input_value())["Units"] == "ms"


def test_cancelling_the_picker_changes_nothing(app_page, studio_url):
    pretend_picker(app_page, "browse-file", "")
    app_page.goto(f"{studio_url}/editor/")

    app_page.click("#jsonFileBtn")
    app_page.wait_for_timeout(500)

    expect(app_page.locator("#editorSection")).to_be_hidden()


def test_a_new_file_is_written_where_the_save_dialog_says(app_page, studio_url, project):
    target = project / "derivatives" / "notes.json"
    target.parent.mkdir()
    pretend_picker(app_page, "browse-save-file", str(target))
    app_page.goto(f"{studio_url}/editor/")
    app_page.click("#newJsonBtn")
    app_page.locator("#jsonEditor").fill('{"note": "hello"}')

    app_page.click("#saveToProjectBtn")

    expect(app_page.locator("#alertContainer")).to_contain_text("Saved to")
    assert json.loads(target.read_text()) == {"note": "hello"}


def test_cancelling_the_save_dialog_writes_nothing(app_page, studio_url, project):
    before = sorted(str(p) for p in project.rglob("*"))
    pretend_picker(app_page, "browse-save-file", "")
    app_page.goto(f"{studio_url}/editor/")
    app_page.click("#newJsonBtn")
    app_page.locator("#jsonEditor").fill('{"note": "hello"}')

    app_page.click("#saveToProjectBtn")
    app_page.wait_for_timeout(500)

    assert sorted(str(p) for p in project.rglob("*")) == before
    expect(app_page.locator("#saveToProjectBtn")).to_be_enabled()
