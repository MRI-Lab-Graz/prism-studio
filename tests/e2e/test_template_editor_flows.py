"""Template editor: the click-through flows that broke by hand.
Each test replays one manual session; add one whenever a new GUI bug turns up."""

from pathlib import Path

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


FOUR_QUESTIONNAIRES = Path(__file__).parents[1] / "data" / "limesurvey_four_questionnaires.lss"


def test_limesurvey_file_with_several_questionnaires_loads_the_chosen_one(page):
    page.click("#btnCreateOpen")  # the import card is collapsed until opened
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))

    expect(page.locator("#excelGroupPickerRow")).to_be_visible()
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(4)
    expect(page.locator("#excelGroupPickerSelect")).to_have_value("g20")  # helper g10 not preselected
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")

    expect(page.locator("#alertArea")).to_contain_text("2 item(s) extracted")
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)  # the item select lists the loaded items

    page.select_option("#sourceSplitSelect", "survey")
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(1)
