"""Template editor: the click-through flows that broke by hand.
Each test replays one manual session; add one whenever a new GUI bug turns up."""

from playwright.sync_api import expect

GLOBAL = "survey-aai.json"


def save_global_copy_to_project(page):
    page.on("dialog", lambda dialog: dialog.accept())  # "Save an editable project copy?"
    page.select_option("#globalTemplateSelect", GLOBAL)
    page.wait_for_selector("#btnValidate:enabled")
    expect(page.locator("#alertArea")).to_contain_text("Valid template")
    page.click("#btnSave")
    expect(page.locator("#alertArea")).to_contain_text("Saved to project library")


def test_saved_global_template_is_selected_in_the_project_dropdown(page):
    save_global_copy_to_project(page)

    expect(page.locator("#projectTemplateSelect")).to_have_value(GLOBAL)


def test_deleted_template_leaves_the_dropdown_without_an_error(page):
    save_global_copy_to_project(page)
    page.select_option("#projectTemplateSelect", GLOBAL)  # Delete only shows for a loaded project file
    expect(page.locator("#btnDelete")).to_be_visible()

    page.click("#btnDelete")

    expect(page.locator("#alertArea")).to_contain_text("Deleted")
    expect(page.locator("#alertArea .alert-danger")).to_have_count(0)
    expect(page.locator(f'#projectTemplateSelect option[value="{GLOBAL}"]')).to_have_count(0)
